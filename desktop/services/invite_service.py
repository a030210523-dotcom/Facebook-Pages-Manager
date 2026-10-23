"""Profile invites — 'add by profile link' the official Meta way.

Why this design (no invented endpoints): Meta does NOT let any app send a Facebook
notification to an arbitrary profile, and no app may read a profile's Pages from a
link alone. Access is only ever granted by the profile owner logging in themselves
and approving the app's permissions. This service implements exactly that, in the
form the admin asked for:

 1. Admin enters the person's name + Facebook profile link -> the app creates an
    invite with an unguessable code and a shareable CONNECT LINK
    ({server}/connect?invite=CODE).
 2. Admin sends that link to the profile owner (Messenger / WhatsApp / email —
    the message comes from the admin, the approval happens on Facebook itself).
 3. The owner opens the link, taps "Continue with Facebook", logs in on
    facebook.com and ACCEPTS the permissions (this is the 'notification/approval'
    step — on Meta's own screens, where Meta requires it to happen).
 4. The server stores the accepted connection against the invite code.
 5. The admin clicks "Check Status": the app imports the profile + ALL its Pages
    and details automatically, stores the token encrypted, and marks the
    invite Connected. Nothing else for the admin to type.

The invite code is the bearer secret for status checks: only someone holding the
code can fetch the result, and the desktop tells the server to wipe the stored
token copy ('consumed') right after importing it.
"""
import secrets
from datetime import datetime, timezone

from ..database.db_manager import DuplicateError
from .sync_service import tasks_to_role

def _now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

def new_invite_code():
    return secrets.token_urlsafe(32)

def connect_link(server_url, code):
    return f"{server_url.rstrip('/')}/connect?invite={code}"

def create_invite(db, display_name=None, profile_link=None, note=None):
    """Creates the local invite record. Returns the invite dict (with its code)."""
    code = new_invite_code()
    iid = db.add_invite(code, display_name=display_name, profile_link=profile_link, note=note)
    return db.get_invite(iid)

def _http(http):
    if http is None:
        import requests; return requests
    return http

def register_invite(server_url, invite, http=None):
    """Tells the server about this invite code (idempotent). Returns True on success."""
    http = _http(http)
    resp = http.post(f"{server_url.rstrip('/')}/api/invites", json={
        "code": invite["code"], "display_name": invite.get("display_name"),
        "profile_link": invite.get("profile_link"), "note": invite.get("note")}, timeout=15)
    return resp.status_code == 200

def import_accepted(db, invite, payload, token_store=None):
    """Imports an accepted invite payload: profile upsert + token + Pages + links.
    payload = {"profile": {"id","name",...}, "pages": [meta page dicts], "access_token": str}
    Returns (profile_id, pages_imported)."""
    me = payload.get("profile") or {}
    fb_id = str(me.get("id") or "")
    if not fb_id: raise ValueError("Accepted invite payload has no profile id")
    existing = [p for p in db.list_profiles() if p.get("facebook_user_id") == fb_id]
    if existing:
        pid = existing[0]["id"]
        db.update_profile(pid, display_name=me.get("name") or existing[0]["display_name"],
                          profile_url=me.get("link") or existing[0].get("profile_url"),
                          connection_status="Connected", authorization_status="Authorized",
                          last_sync_at=_now())
    else:
        pid = db.add_profile(me.get("name") or "Facebook User", facebook_user_id=fb_id,
                             profile_url=me.get("link") or f"https://www.facebook.com/{fb_id}",
                             connection_status="Connected")
        db.update_profile(pid, authorization_status="Authorized", last_sync_at=_now())
    token = payload.get("access_token")
    if token and token_store is not None:
        token_store.set_token(f"profile:{pid}", token, kind="user")
    imported = 0
    for p in payload.get("pages") or []:
        page_fb_id = str(p.get("id") or "")
        if not page_fb_id: continue
        found = [r for r in db.list_pages(search=page_fb_id) if r["facebook_page_id"] == page_fb_id]
        if found:
            pgid = found[0]["id"]
            db.update_page(pgid, page_name=p.get("name") or found[0]["page_name"],
                           page_url=p.get("link"), category=p.get("category"),
                           follower_count=p.get("fan_count"), last_checked_at=_now())
        else:
            try:
                pgid = db.add_page(page_fb_id, p.get("name") or f"Page {page_fb_id}",
                                   page_url=p.get("link"), category=p.get("category"),
                                   follower_count=p.get("fan_count"),
                                   manual_status="Active", data_source="meta_api")
            except DuplicateError:
                pgid = [r for r in db.list_pages() if r["facebook_page_id"] == page_fb_id][0]["id"]
        db.link_profile_page(pid, pgid, access_role=tasks_to_role(p.get("tasks")),
                             access_status="Active")
        if token_store is not None and p.get("access_token"):
            token_store.set_token(f"page:{pgid}", p["access_token"], kind="page")
        db.record_health(pgid, technical="Healthy", policy="Unknown",
                         restriction="Unknown", source="meta_api")
        imported += 1
    db.update_invite(invite["id"], status="Connected", profile_id=pid, accepted_at=_now())
    db.add_sync_log(pid, "Success", imported, "Profile added via invite link (auto-import)")
    return pid, imported

def check_invite(db, server_url, invite_id, token_store=None, http=None):
    """Polls the server for one invite. On acceptance imports everything and asks
    the server to wipe its token copy. Returns a status dict; never raises for
    network/API problems — they come back as {"status": "Error", "error": ...}."""
    http = _http(http)
    invite = db.get_invite(invite_id)
    if invite is None: return {"status": "Error", "error": "Invite not found"}
    if invite["status"] == "Connected":
        return {"status": "Connected", "profile_id": invite.get("profile_id")}
    base = server_url.rstrip("/")
    try:
        register_invite(base, invite, http=http)  # idempotent; safe if already registered
        resp = http.get(f"{base}/api/invites/{invite['code']}", timeout=15)
        if resp.status_code == 404:
            return {"status": "Pending", "note": "Invite not registered on the server yet"}
        if resp.status_code != 200:
            return {"status": "Error", "error": f"Server returned HTTP {resp.status_code}"}
        data = resp.json()
    except Exception as e:
        return {"status": "Error", "error": f"Could not reach the server: {e}"}
    if data.get("status") != "accepted":
        return {"status": "Pending"}
    try:
        pid, imported = import_accepted(db, invite, data, token_store=token_store)
    except Exception as e:
        return {"status": "Error", "error": f"Import failed: {e}"}
    try:  # best effort: server wipes its stored token copy once we have imported it
        http.post(f"{base}/api/invites/{invite['code']}/consumed", timeout=10)
    except Exception:
        pass
    return {"status": "Connected", "profile_id": pid, "pages_imported": imported}
