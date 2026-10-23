"""Monetization service (Section 7, Phase 3).

Reality, documented honestly: Meta does not expose a general Graph API endpoint that
returns an arbitrary Page's monetization eligibility/restrictions to third-party apps
with the standard permissions. Therefore:
 - api_status stays 'Unknown' with data_source 'meta_api_limitation' — never inferred
   from follower count, never guessed.
 - The supported workflow is MANUAL verification (Meta Business Suite / Creator Studio):
   a human checks the official dashboard and records the result here, stored separately
   (manual_status + verified date + notes) with its own history."""
LIMITATION_MESSAGE = ("Monetization eligibility is not available through the current Meta API "
                      "permissions. Verify in Meta Business Suite and record the result manually.")
OFFICIAL_DASHBOARD_URL = "https://business.facebook.com/content-monetization"

def check_monetization(db, page_row):
    """Records an API-attempt entry that honestly reports the limitation."""
    db.record_monetization(page_row["id"], api_status="Unknown", eligibility="Unknown",
                           source="meta_api_limitation",
                           manual_status=db.latest_monetization(page_row["id"])["manual_status"],
                           notes=LIMITATION_MESSAGE)
    return db.latest_monetization(page_row["id"])

MANUAL_STATUSES = ["Not Verified", "Manually Verified - Eligible", "Manually Verified - Not Eligible",
                   "Manually Verified - Restricted", "In Review"]

def record_manual_verification(db, page_id, manual_status, notes=None, eligibility="Unknown"):
    if manual_status not in MANUAL_STATUSES: raise ValueError("Invalid manual status")
    if eligibility not in ("Unknown", "Eligible", "Not Eligible", "Restricted"):
        raise ValueError("Invalid eligibility value")
    db.record_monetization(page_id, api_status="Unknown", eligibility=eligibility,
                           source="manual_verification", manual_status=manual_status, notes=notes)
    return db.latest_monetization(page_id)

def monetization_summary(db):
    known = unknown = manual_verified = 0
    for p in db.list_pages():
        m = db.latest_monetization(p["id"])
        if m["api_status"] != "Unknown": known += 1
        else: unknown += 1
        if str(m["manual_status"]).startswith("Manually Verified"): manual_verified += 1
    return {"api_known": known, "api_unknown": unknown, "manually_verified": manual_verified,
            "limitation": LIMITATION_MESSAGE, "dashboard": OFFICIAL_DASHBOARD_URL}
