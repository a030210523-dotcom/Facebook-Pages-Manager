"""FastAPI licensing server (Sections 15/18/23, Phase 4/5). Run:
  uvicorn licensing_server.main:app --host 0.0.0.0 --port 8000
Server-only env (NEVER in the desktop app):
  FPM_ED25519_PRIVATE_KEY  license signing key (production). Generate: see licensing_server/signing.py
  FPM_SIGNING_SECRET       dev-only HMAC fallback
  FPM_ADMIN_TOKEN          bootstrap/emergency admin token (rotate after Super Admin setup)
  FPM_LICENSE_DB           SQLite path for dev; production PostgreSQL plan in docs/DEPLOYMENT.md
  META_APP_ID / META_APP_SECRET / META_API_VERSION   for /api/meta/token-exchange
RBAC is enforced SERVER-side: admin endpoints need the bootstrap token OR a session
token whose user role is Admin/Super Admin; destructive actions need Super Admin."""
import os, time
from collections import defaultdict, deque
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from .core import LicenseStore
from .users import UserStore
from .invites import InviteStore

app = FastAPI(title="Facebook Pages Manager — Licensing Server", version="0.4.0")

def store():
    # Fresh connection per request: sqlite connections are thread-bound, FastAPI uses a threadpool.
    return LicenseStore(os.environ.get("FPM_LICENSE_DB", "./licenses.db"),
                        os.environ.get("FPM_SIGNING_SECRET") or None,
                        os.environ.get("FPM_ED25519_PRIVATE_KEY") or None)

def users():
    return UserStore(os.environ.get("FPM_LICENSE_DB", "./licenses.db"))

def invites():
    return InviteStore(os.environ.get("FPM_LICENSE_DB", "./licenses.db"))

ADMIN_TOKEN = lambda: os.environ.get("FPM_ADMIN_TOKEN", "")

# --- simple in-memory rate limiting (per IP + route group). Production: also put a
# --- reverse proxy limiter in front (see docs/DEPLOYMENT.md). ---
_hits = defaultdict(deque)
LIMITS = {"/api/auth/login": (10, 60), "/api/license/": (60, 60), "/api/meta/": (30, 60),
          "/api/invites": (30, 60), "/connect": (30, 60), "/auth/facebook/": (30, 60)}
@app.middleware("http")
async def rate_limit(request: Request, call_next):
    for prefix, (limit, window) in LIMITS.items():
        if request.url.path.startswith(prefix):
            key = f"{request.client.host}:{prefix}"; now = time.time(); q = _hits[key]
            while q and q[0] < now - window: q.popleft()
            if len(q) >= limit:
                return JSONResponse({"detail": "Rate limit exceeded. Try again later."}, status_code=429)
            q.append(now)
    return await call_next(request)

def _session_user(authorization):
    if authorization and authorization.startswith("Bearer "):
        return users().user_for_token(authorization[7:])
    return None

def require_admin(x_admin_token: str = "", authorization: str = ""):
    if ADMIN_TOKEN() and x_admin_token == ADMIN_TOKEN(): return "bootstrap-token"
    u = _session_user(authorization)
    if u and u["role"] in ("Admin", "Super Admin"): return u["username"]
    raise HTTPException(403, "Admin authorization required")

def require_super_admin(x_admin_token: str = "", authorization: str = ""):
    if ADMIN_TOKEN() and x_admin_token == ADMIN_TOKEN(): return "bootstrap-token"
    u = _session_user(authorization)
    if u and u["role"] == "Super Admin": return u["username"]
    raise HTTPException(403, "Super Admin authorization required")

class ActivateIn(BaseModel):
    license_key: str; installation_id: str; device_label: str | None = None; app_version: str | None = None
class ValidateIn(BaseModel):
    license_key: str; installation_id: str
class CreateIn(BaseModel):
    customer_name: str; license_type: str = "30 days"; max_devices: int = 1
    customer_email: str | None = None; customer_phone: str | None = None
class LoginIn(BaseModel):
    username: str; password: str
class CreateUserIn(BaseModel):
    username: str; password: str; role: str = "Licensed User"
class MetaExchangeIn(BaseModel):
    code: str; redirect_uri: str
class InviteIn(BaseModel):
    code: str; display_name: str | None = None; profile_link: str | None = None; note: str | None = None

@app.get("/health")
def health(): return {"status": "ok", "service": "fpm-licensing", "version": "0.4.0"}

@app.get("/api/license/public-key")
def public_key():
    priv = os.environ.get("FPM_ED25519_PRIVATE_KEY")
    if priv:
        from .signing import public_key_from_private
        return {"alg": "ed25519", "public_key": public_key_from_private(priv)}
    return {"alg": "hmac-sha256", "public_key": None,
            "warning": "Server is in DEV HMAC mode — set FPM_ED25519_PRIVATE_KEY for production."}

# ---------- Auth (Section 15) ----------
@app.post("/api/auth/bootstrap-super-admin")
def bootstrap(body: CreateUserIn, x_admin_token: str = Header(default="")):
    if not ADMIN_TOKEN() or x_admin_token != ADMIN_TOKEN():
        raise HTTPException(403, "Bootstrap token required")
    try:
        uid = users().bootstrap_super_admin(body.username, body.password)
    except PermissionError as e: raise HTTPException(409, str(e))
    except ValueError as e: raise HTTPException(400, str(e))
    return {"ok": True, "user_id": uid, "role": "Super Admin"}

@app.post("/api/auth/login")
def login(body: LoginIn):
    r = users().login(body.username, body.password)
    if not r: raise HTTPException(401, "Invalid credentials, account inactive, or temporarily locked after failed attempts")
    return r

@app.post("/api/admin/users")
def create_user(body: CreateUserIn, x_admin_token: str = Header(default=""),
                authorization: str = Header(default="")):
    actor = require_super_admin(x_admin_token, authorization)
    try: uid = users().create_user(actor, body.username, body.password, body.role)
    except ValueError as e: raise HTTPException(400, str(e))
    return {"ok": True, "user_id": uid}

# ---------- Meta token exchange (App Secret stays on server) ----------
@app.post("/api/meta/token-exchange")
def meta_token_exchange(body: MetaExchangeIn):
    from .meta_exchange import exchange_code
    try: data = exchange_code(body.code, body.redirect_uri)
    except RuntimeError as e: raise HTTPException(400, str(e))
    return {"access_token": data["access_token"], "token_type": data.get("token_type", "bearer"),
            "expires_in": data.get("expires_in")}

# ---------- Profile invites (connect-by-link) ----------
# Flow: the admin's desktop generates an unguessable invite code and registers it
# here; the profile owner opens {server}/connect?invite=CODE, approves on
# Facebook's own login screens, and this server stores the accepted connection
# against the code until the desktop fetches it once (then the token copy here
# is wiped via /consumed). No Facebook passwords are ever collected — the owner
# logs in on facebook.com only (official OAuth, App Secret stays server-side).
def _public_base(request: Request):
    return (os.environ.get("FPM_PUBLIC_BASE_URL") or str(request.base_url)).rstrip("/")

def _html_page(title, body):
    return HTMLResponse(
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{title}</title></head>"
        "<body style='font-family:Segoe UI,Arial,sans-serif;max-width:520px;margin:60px auto;"
        "padding:24px;color:#1c2b3a'><h2 style='color:#1877F2'>Facebook Pages Manager</h2>"
        f"{body}</body></html>")

@app.post("/api/invites")
def register_invite(body: InviteIn):
    if len(body.code) < 16: raise HTTPException(400, "Invite code is too short")
    row = invites().register(body.code, body.display_name, body.profile_link, body.note)
    return {"ok": True, "status": row["status"]}

@app.get("/api/invites/{code}")
def invite_status(code: str):
    row = invites().get(code)
    if row is None: raise HTTPException(404, "Invite not found")
    return invites().public_view(row)

@app.post("/api/invites/{code}/consumed")
def invite_consumed(code: str):
    if not invites().mark_consumed(code): raise HTTPException(404, "Invite not found")
    return {"ok": True}

@app.get("/connect")
def connect_page(request: Request, invite: str = ""):
    inv = invites()
    row = inv.get(invite) if invite else None
    if row is None:
        return _html_page("Invalid link", "<p>This connect link is invalid or has expired. "
                          "Please ask the admin to send you a new invite link.</p>")
    if row["status"] in ("accepted", "consumed"):
        return _html_page("Already connected", "<p>This profile is already connected. "
                          "You can close this tab.</p>")
    app_id = os.environ.get("META_APP_ID", "")
    if not app_id:
        return _html_page("Not configured yet", "<p>The Meta app is not configured on this "
                          "server yet. Please tell the admin to finish the Meta setup first.</p>")
    import urllib.parse
    redirect_uri = f"{_public_base(request)}/auth/facebook/callback"
    dialog = "https://www.facebook.com/" + os.environ.get("META_API_VERSION", "v21.0") + "/dialog/oauth?" + urllib.parse.urlencode({
        "client_id": app_id, "redirect_uri": redirect_uri, "state": invite,
        "scope": "public_profile,pages_show_list,pages_read_engagement", "response_type": "code"})
    who = f" for <b>{row['display_name']}</b>" if row.get("display_name") else ""
    return _html_page("Connect your Facebook profile",
        f"<p>You have been invited to connect your Facebook profile{who} with "
        "Facebook Pages Manager.</p><p>Tapping the button opens Facebook's official "
        "login. You will log in on <b>facebook.com</b> and choose what to share — "
        "this app never sees your Facebook password.</p>"
        f"<p><a href='{dialog}' style='display:inline-block;background:#1877F2;color:#fff;"
        "padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:600'>"
        "Continue with Facebook</a></p>")

@app.get("/auth/facebook/callback")
def facebook_callback(request: Request, code: str = "", state: str = "",
                      error: str = "", error_description: str = ""):
    if error:
        return _html_page("Connection cancelled",
                          f"<p>Facebook reported: {error_description or error}. Nothing was connected.</p>")
    inv = invites()
    if not code or inv.get(state) is None:
        return _html_page("Invalid request", "<p>This connection link is invalid or has expired.</p>")
    from .meta_exchange import exchange_code, fetch_profile_and_pages
    redirect_uri = f"{_public_base(request)}/auth/facebook/callback"
    try:
        data = exchange_code(code, redirect_uri)
        payload = fetch_profile_and_pages(data["access_token"])
    except RuntimeError as e:
        return _html_page("Connection failed", f"<p>{e}</p><p>Please ask the admin for a new invite link.</p>")
    payload["access_token"] = data["access_token"]
    inv.mark_accepted(state, payload)
    name = (payload.get("profile") or {}).get("name", "your profile")
    pages_n = len(payload.get("pages") or [])
    return _html_page("Connected!",
        f"<p><b>{name}</b> is now connected, along with {pages_n} Page(s). "
        "Everything will appear automatically in Facebook Pages Manager. "
        "You can close this tab.</p>")

# ---------- Licensing ----------
@app.post("/api/license/activate")
def activate(body: ActivateIn):
    r = store().activate(body.license_key, body.installation_id, body.device_label, body.app_version)
    if not r["ok"]: raise HTTPException(400, r["error"])
    return r

@app.post("/api/license/validate")
def validate(body: ValidateIn):
    r = store().validate(body.license_key, body.installation_id)
    if not r["ok"]: raise HTTPException(400, r["error"])
    return r

@app.post("/api/license/deactivate")
def deactivate_own(body: ValidateIn):
    s = store(); lic = s._find(body.license_key)
    if lic is None: raise HTTPException(404, "License not found")
    row = s.conn.execute("SELECT id FROM activations WHERE license_id=? AND installation_id=?",
                         (lic["id"], body.installation_id)).fetchone()
    if not row: raise HTTPException(404, "Activation not found")
    s.deactivate_device("customer", row["id"]); return {"ok": True}

@app.post("/api/admin/licenses")
def create(body: CreateIn, x_admin_token: str = Header(default=""), authorization: str = Header(default="")):
    actor = require_admin(x_admin_token, authorization)
    return store().create_license(actor, body.customer_name, body.license_type,
                                  body.max_devices, body.customer_email, body.customer_phone)

@app.get("/api/admin/licenses")
def list_licenses(status: str | None = None, search: str | None = None,
                  x_admin_token: str = Header(default=""), authorization: str = Header(default="")):
    require_admin(x_admin_token, authorization); return store().list_licenses(status, search)

@app.post("/api/admin/licenses/{lid}/suspend")
def suspend(lid: int, x_admin_token: str = Header(default=""), authorization: str = Header(default="")):
    actor = require_super_admin(x_admin_token, authorization); store().suspend(actor, lid); return {"ok": True}

@app.post("/api/admin/licenses/{lid}/revoke")
def revoke(lid: int, x_admin_token: str = Header(default=""), authorization: str = Header(default="")):
    actor = require_super_admin(x_admin_token, authorization); store().revoke(actor, lid); return {"ok": True}

@app.post("/api/admin/licenses/{lid}/renew")
def renew(lid: int, extra_days: int = 30, x_admin_token: str = Header(default=""),
          authorization: str = Header(default="")):
    actor = require_super_admin(x_admin_token, authorization)
    return {"ok": True, "new_expiry": store().renew(actor, lid, extra_days)}

@app.post("/api/admin/activations/{aid}/deactivate")
def deactivate(aid: int, x_admin_token: str = Header(default=""), authorization: str = Header(default="")):
    actor = require_super_admin(x_admin_token, authorization); store().deactivate_device(actor, aid); return {"ok": True}

@app.get("/api/admin/stats")
def stats(x_admin_token: str = Header(default=""), authorization: str = Header(default="")):
    require_admin(x_admin_token, authorization); return store().stats()
