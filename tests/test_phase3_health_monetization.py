import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from desktop.database.db_manager import DBManager
from desktop.services import health_service as hs
from desktop.services import monetization_service as ms
from desktop.services.meta_api import TokenExpiredError, PermissionMissingError

@pytest.fixture()
def db(tmp_path):
    d = DBManager(str(tmp_path / "h.db")); yield d; d.close()

class OkClient:
    def get_page(self, pid): return {"id": pid, "name": "P"}
class ExpiredClient:
    def get_page(self, pid): raise TokenExpiredError("expired", 190)
class PermClient:
    def get_page(self, pid): raise PermissionMissingError("no perm", 200)

def row(db, pgid): return [r for r in db.list_pages() if r["id"] == pgid][0]

def test_technical_check_healthy_but_policy_not_claimed(db):
    pg = db.add_page("1", "Page One")
    h = hs.check_page_health(db, row(db, pg), OkClient())
    assert h["technical_connection_status"] == "Healthy"
    # Crucial honesty rule: API success must NOT mark the Page policy-compliant
    assert h["policy_status"] == "Unknown" and h["restriction_status"] == "Manual Check Required"

def test_no_token_means_manual_check_required(db):
    pg = db.add_page("2", "No Token Page")
    h = hs.check_page_health(db, row(db, pg), None)
    assert h["technical_connection_status"] == "Manual Check Required"

def test_expired_and_permission_mapping(db):
    pg = db.add_page("3", "Exp Page")
    assert hs.check_page_health(db, row(db, pg), ExpiredClient())["technical_connection_status"] == "Connection Error"
    pg2 = db.add_page("4", "Perm Page")
    assert hs.check_page_health(db, row(db, pg2), PermClient())["technical_connection_status"] == "Permission Missing"

def test_manual_health_recorded_separately(db):
    pg = db.add_page("5", "Manual Page")
    hs.check_page_health(db, row(db, pg), OkClient())
    h = hs.record_manual_health(db, pg, "Restricted", "Restricted", notes="Seen in Business Suite")
    assert h["policy_status"] == "Restricted" and h["data_source"] == "manual_verification"
    assert len(db.health_history(pg)) == 2

def test_check_all_summary(db):
    db.add_page("6", "A"); db.add_page("7", "B")
    summary = hs.check_all_pages(db, lambda row: OkClient())
    assert summary == {"Healthy": 2}

def test_monetization_never_inferred_from_followers(db):
    pg = db.add_page("8", "Rich Page", follower_count=10_000_000)
    m = ms.check_monetization(db, {"id": pg})
    assert m["api_status"] == "Unknown" and m["eligibility_status"] == "Unknown"
    assert "not available" in ms.LIMITATION_MESSAGE

def test_manual_monetization_verification(db):
    pg = db.add_page("9", "Monet Page")
    m = ms.record_manual_verification(db, pg, "Manually Verified - Eligible", eligibility="Eligible", notes="Checked 2026-10-21")
    assert m["manual_status"] == "Manually Verified - Eligible" and m["data_source"] == "manual_verification"
    s = ms.monetization_summary(db)
    assert s["manually_verified"] == 1 and s["api_unknown"] == 1
    with pytest.raises(ValueError): ms.record_manual_verification(db, pg, "Definitely Eligible Trust Me")
