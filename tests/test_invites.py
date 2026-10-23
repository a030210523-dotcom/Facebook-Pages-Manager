"""Invite-by-link flow: desktop CRUD + auto-import, server endpoints, /connect pages."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from desktop.database.db_manager import DBManager, DuplicateError
from desktop.services import invite_service as inv
from desktop.services.token_store import TokenStore


class FakeResp:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code; self._payload = payload or {}
    def json(self): return self._payload


class FakeHTTP:
    """Mimics the server invite API for desktop-side tests."""
    def __init__(self, status_payload):
        self.status_payload = status_payload; self.calls = []
    def post(self, url, json=None, timeout=None):
        self.calls.append(("POST", url)); return FakeResp(200, {"ok": True})
    def get(self, url, timeout=None):
        self.calls.append(("GET", url)); return FakeResp(200, self.status_payload)


def make_db(tmp_path):
    return DBManager(str(tmp_path / "t.db"))


def test_invite_db_crud(tmp_path):
    db = make_db(tmp_path)
    iid = db.add_invite("code-1234567890abcdef", display_name="Ali", profile_link="https://facebook.com/ali")
    rows = db.list_invites()
    assert len(rows) == 1 and rows[0]["status"] == "Pending"
    with pytest.raises(DuplicateError):
        db.add_invite("code-1234567890abcdef")
    db.update_invite(iid, status="Connected", profile_id=7)
    assert db.get_invite(iid)["profile_id"] == 7
    db.delete_invite(iid)
    assert db.list_invites() == []


def test_create_invite_and_link(tmp_path):
    db = make_db(tmp_path)
    invite = inv.create_invite(db, "Ali", "https://facebook.com/ali")
    assert len(invite["code"]) >= 32
    link = inv.connect_link("https://srv.example:8000/", invite["code"])
    assert link == f"https://srv.example:8000/connect?invite={invite['code']}"


def test_check_invite_pending(tmp_path):
    db = make_db(tmp_path)
    invite = inv.create_invite(db, "Ali", None)
    http = FakeHTTP({"status": "pending"})
    out = inv.check_invite(db, "http://srv", invite["id"], http=http)
    assert out["status"] == "Pending"
    assert db.get_invite(invite["id"])["status"] == "Pending"


def test_check_invite_accepted_auto_imports(tmp_path):
    db = make_db(tmp_path)
    invite = inv.create_invite(db, "Ali", None)
    payload = {
        "status": "accepted",
        "profile": {"id": "555", "name": "Ali Raza"},
        "pages": [
            {"id": "9001", "name": "Ali Shop", "link": "https://facebook.com/alishop",
             "category": "Store", "fan_count": 1200, "tasks": ["MANAGE"], "access_token": "PAGE_TOK"},
            {"id": "9002", "name": "Ali Blog", "category": "Blog", "fan_count": 30,
             "tasks": ["ANALYZE"], "access_token": "PAGE_TOK2"},
        ],
        "access_token": "USER_TOK",
    }
    http = FakeHTTP(payload)
    ts = TokenStore(str(tmp_path / "tokens.enc"), str(tmp_path / "tokens.key"))
    out = inv.check_invite(db, "http://srv", invite["id"], token_store=ts, http=http)
    assert out["status"] == "Connected" and out["pages_imported"] == 2
    profiles = db.list_profiles()
    assert len(profiles) == 1
    p = profiles[0]
    assert p["facebook_user_id"] == "555" and p["connection_status"] == "Connected"
    assert p["authorization_status"] == "Authorized"
    pages = db.list_pages(profile_id=p["id"])
    assert {pg["facebook_page_id"] for pg in pages} == {"9001", "9002"}
    assert ts.get_token(f"profile:{p['id']}") == "USER_TOK"
    assert db.get_invite(invite["id"])["status"] == "Connected"
    assert any(url.endswith("/consumed") for method, url in http.calls if method == "POST")
    # second check is a no-op (already connected locally)
    assert inv.check_invite(db, "http://srv", invite["id"], http=http)["status"] == "Connected"


def test_profile_details_view(tmp_path):
    db = make_db(tmp_path)
    pid = db.add_profile("Ali Raza", facebook_user_id="555", connection_status="Connected")
    other = db.add_profile("Second Person", facebook_user_id="777")  # multiple profiles coexist
    pg1 = db.add_page("9001", "Ali Shop", category="Store", follower_count=1200)
    pg2 = db.add_page("9002", "Ali Blog", category="Blog", follower_count=300)
    db.link_profile_page(pid, pg1, access_role="Admin (Manage)", access_status="Active")
    db.link_profile_page(pid, pg2, access_role="Analyst", access_status="Active")
    db.record_health(pg1, technical="Healthy", restriction="None", source="meta_api")
    db.record_health(pg2, technical="Warning", restriction="Restricted", source="meta_api")
    db.record_monetization(pg1, manual_status="Verified")
    d = db.profile_details(pid)
    assert d["display_name"] == "Ali Raza" and d["connection_status"] == "Connected"
    assert d["summary"] == {"page_count": 2, "total_followers": 1500,
                            "healthy_pages": 1, "restricted_pages": 1, "needs_check_pages": 1}
    by_id = {p["facebook_page_id"]: p for p in d["pages"]}
    assert by_id["9001"]["access_role"] == "Admin (Manage)"
    assert by_id["9001"]["health_status"] == "Healthy"
    assert by_id["9001"]["monetization_status"] == "Verified"
    assert by_id["9002"]["restriction_status"] == "Restricted"
    # profiles stay independent; unknown id -> None
    assert db.profile_details(other)["summary"]["page_count"] == 0
    assert db.profile_details(99999) is None


def _server_client(tmp_path, monkeypatch):
    monkeypatch.setenv("FPM_LICENSE_DB", str(tmp_path / "srv.db"))
    monkeypatch.setenv("META_APP_ID", "1234567890")
    monkeypatch.setenv("META_APP_SECRET", "shh")
    from fastapi.testclient import TestClient
    from licensing_server.main import app
    return TestClient(app)


def test_server_invite_flow(tmp_path, monkeypatch):
    c = _server_client(tmp_path, monkeypatch)
    code = "invite-code-0123456789abcdef"
    assert c.post("/api/invites", json={"code": "short"}).status_code == 400
    r = c.post("/api/invites", json={"code": code, "display_name": "Ali",
                                    "profile_link": "https://facebook.com/ali"})
    assert r.status_code == 200
    assert c.get(f"/api/invites/{code}").json()["status"] == "pending"
    # /connect page points at Facebook's dialog with the invite code as state
    page = c.get(f"/connect?invite={code}")
    assert page.status_code == 200 and "Continue with Facebook" in page.text
    assert "facebook.com" in page.text and f"state={code}" in page.text
    assert c.get("/connect?invite=does-not-exist-000000").text.find("invalid") >= 0
    # owner completes Facebook login -> callback stores the accepted payload
    import licensing_server.meta_exchange as mx
    monkeypatch.setattr(mx, "exchange_code",
                        lambda code_, redirect_uri: {"access_token": "LONG_TOK", "expires_in": 9999})
    monkeypatch.setattr(mx, "fetch_profile_and_pages",
                        lambda token: {"profile": {"id": "555", "name": "Ali Raza"},
                                       "pages": [{"id": "9001", "name": "Ali Shop", "tasks": ["MANAGE"]}]})
    cb = c.get(f"/auth/facebook/callback?code=AUTHCODE&state={code}")
    assert cb.status_code == 200 and "Connected" in cb.text
    got = c.get(f"/api/invites/{code}").json()
    assert got["status"] == "accepted" and got["profile"]["id"] == "555"
    assert got["access_token"] == "LONG_TOK" and got["pages"][0]["id"] == "9001"
    # desktop consumed it -> token copy wiped on the server
    assert c.post(f"/api/invites/{code}/consumed").status_code == 200
    after = c.get(f"/api/invites/{code}").json()
    assert after["status"] == "consumed" and "access_token" not in after


def test_fetch_profile_and_pages_paging():
    from licensing_server.meta_exchange import fetch_profile_and_pages
    calls = []
    class R:
        def __init__(self, payload): self._p = payload
        def json(self): return self._p
    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append(url)
        if url.endswith("/me"):
            return R({"id": "1", "name": "Owner"})
        if "me/accounts" in url and params:
            return R({"data": [{"id": "10"}], "paging": {"next": "https://graph.facebook.com/v21.0/me/accounts?after=x"}})
        return R({"data": [{"id": "11"}]})
    out = fetch_profile_and_pages("TOK", http_get=fake_get)
    assert out["profile"]["id"] == "1"
    assert [p["id"] for p in out["pages"]] == ["10", "11"]
