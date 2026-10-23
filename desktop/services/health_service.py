"""Page Health service (Section 6, Phase 3).

Technical connection health IS checkable via the documented API: fetching the Page
with a valid Page/user token proves the authorized connection works.
Policy/account health is NOT exposed by a general documented Graph API endpoint for
arbitrary Pages — so policy/restriction stay 'Unknown' / 'Manual Check Required'
unless a human records a manual verification. We never call a Page policy-compliant
just because an API call succeeded, and we never invent restriction data."""
from .meta_api import TokenExpiredError, PermissionMissingError, RateLimitError, MetaAPIError

TECH_STATUSES = ["Healthy", "Warning", "Restricted", "Connection Error",
                 "Permission Missing", "Unknown", "Manual Check Required"]

def check_page_health(db, page_row, client):
    """client: MetaAPIClient built with the Page token, or None if no token is stored.
    Returns the recorded health dict."""
    pgid = page_row["id"]
    if client is None:
        db.record_health(pgid, technical="Manual Check Required", policy="Unknown",
                         restriction="Manual Check Required",
                         error="No stored access token for this Page — connect the profile first.",
                         source="system")
        return db.latest_health(pgid)
    try:
        data = client.get_page(page_row["facebook_page_id"])
        if data and data.get("id"):
            db.record_health(pgid, technical="Healthy", policy="Unknown",
                             restriction="Manual Check Required",
                             error=None, source="meta_api")
        else:
            db.record_health(pgid, technical="Warning", policy="Unknown",
                             restriction="Manual Check Required",
                             error="API returned no Page data.", source="meta_api")
    except TokenExpiredError as e:
        db.record_health(pgid, technical="Connection Error", policy="Unknown",
                         restriction="Unknown", error=f"Token expired/invalid: {e}", source="meta_api")
    except PermissionMissingError as e:
        db.record_health(pgid, technical="Permission Missing", policy="Unknown",
                         restriction="Unknown", error=str(e), source="meta_api")
    except RateLimitError as e:
        db.record_health(pgid, technical="Warning", policy="Unknown",
                         restriction="Unknown", error=f"Rate limited: {e}", source="meta_api")
    except MetaAPIError as e:
        db.record_health(pgid, technical="Connection Error", policy="Unknown",
                         restriction="Unknown", error=str(e), source="meta_api")
    return db.latest_health(pgid)

def record_manual_health(db, page_id, policy_status, restriction_status, notes=None):
    """Manual verification workflow — clearly sourced as manual, kept separate from API data."""
    if policy_status not in ("Healthy", "Warning", "Restricted", "Unknown"):
        raise ValueError("Invalid policy status")
    if restriction_status not in ("None Known", "Restricted", "Unknown"):
        raise ValueError("Invalid restriction status")
    db.record_health(page_id, technical=db.latest_health(page_id)["technical_connection_status"],
                     policy=policy_status, restriction=restriction_status,
                     error=notes, source="manual_verification")
    return db.latest_health(page_id)

def check_all_pages(db, client_factory):
    """client_factory(page_row) -> MetaAPIClient | None. Returns summary counts."""
    summary = {}
    for p in db.list_pages():
        h = check_page_health(db, p, client_factory(p))
        summary[h["technical_connection_status"]] = summary.get(h["technical_connection_status"], 0) + 1
    return summary
