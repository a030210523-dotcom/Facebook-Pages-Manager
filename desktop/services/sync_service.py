"""Synchronization engine (Section 10). Discovers authorized Pages via /me/accounts,
upserts by stable Page ID (no duplicates), links profile<->page access from `tasks`,
flags Pages that vanished from the response as missing (never deletes), records
sync logs, tolerates partial failure, and updates the profile's sync status.
Designed to run in a background worker (QThread) in the UI; here it is a plain
service so it is fully testable with a mocked MetaAPIClient."""
from datetime import datetime, timezone
from ..database.db_manager import DuplicateError
from .meta_api import MetaAPIError, TokenExpiredError, PermissionMissingError

def _now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

# Meta `tasks` on a Page (documented): MANAGE, CREATE_CONTENT, MODERATE, ADVERTISE, ANALYZE
def tasks_to_role(tasks):
    if not tasks: return "Unknown"
    if "MANAGE" in tasks: return "Admin (Manage)"
    if "CREATE_CONTENT" in tasks: return "Editor (Create Content)"
    if "MODERATE" in tasks: return "Moderator"
    if "ADVERTISE" in tasks: return "Advertiser"
    if "ANALYZE" in tasks: return "Analyst"
    return ", ".join(tasks)

def sync_profile_pages(db, profile_id, client, token_store=None):
    """Returns a result dict; never raises for API errors — they are logged & returned."""
    started = _now(); processed = 0; errors = []
    try:
        api_pages = client.get_my_pages()
    except TokenExpiredError as e:
        db.update_profile(profile_id, connection_status="Error", authorization_status="Token Expired")
        db.add_sync_log(profile_id, "Failed", 0, f"Token expired/invalid: {e}", started)
        return {"ok": False, "result": "Failed", "pages_processed": 0, "errors": [str(e)]}
    except PermissionMissingError as e:
        db.update_profile(profile_id, connection_status="Error", authorization_status="Permission Missing")
        db.add_sync_log(profile_id, "Failed", 0, f"Permission missing: {e}", started)
        return {"ok": False, "result": "Failed", "pages_processed": 0, "errors": [str(e)]}
    except MetaAPIError as e:
        db.add_sync_log(profile_id, "Failed", 0, str(e), started)
        return {"ok": False, "result": "Failed", "pages_processed": 0, "errors": [str(e)]}

    seen_ids = set()
    for p in api_pages:
        page_fb_id = str(p.get("id") or "")
        if not page_fb_id: errors.append("Skipped a Page entry with no ID"); continue
        seen_ids.add(page_fb_id)
        try:
            existing = [r for r in db.list_pages(search=page_fb_id) if r["facebook_page_id"] == page_fb_id]
            if existing:
                pgid = existing[0]["id"]
                db.update_page(pgid, page_name=p.get("name") or existing[0]["page_name"],
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
            db.link_profile_page(profile_id, pgid, access_role=tasks_to_role(p.get("tasks")),
                                 access_status="Active")
            if token_store is not None and p.get("access_token"):
                # Page access token -> encrypted store only; never DB plain text, never logs.
                token_store.set_token(f"page:{pgid}", p["access_token"], kind="page")
            db.record_health(pgid, technical="Healthy", policy="Unknown", restriction="Unknown",
                             source="meta_api")
            processed += 1
        except Exception as e:  # partial failure: keep going with other Pages
            errors.append(f"Page {page_fb_id}: {e}")

    missing = db.mark_missing_pages(profile_id, seen_ids)
    result = "Success" if not errors else "Partial"
    db.update_profile(profile_id, connection_status="Connected", authorization_status="Authorized",
                      last_sync_at=_now())
    db.add_sync_log(profile_id, result, processed,
                    ("; ".join(errors) if errors else None), started)
    return {"ok": True, "result": result, "pages_processed": processed,
            "missing_flagged": missing, "errors": errors}
