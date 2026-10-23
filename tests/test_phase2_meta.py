import os, sys, threading, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from desktop.database.db_manager import DBManager
from desktop.services.meta_api import (MetaAPIClient, TokenExpiredError, PermissionMissingError,
                                       RateLimitError, MetaAPIError)
from desktop.services.sync_service import sync_profile_pages, tasks_to_role
from desktop.services import oauth_service as oauth
from desktop.services.token_store import TokenStore

class FakeResp:
    def __init__(self, status, data): self.status_code = status; self._d = data
    def json(self): return self._d

class FakeSession:
    def __init__(self, script): self.script = list(script); self.calls = []
    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        item = self.script.pop(0)
        return item(url) if callable(item) else item

PAGE1 = {"id": "111", "name": "Alpha Page", "category": "Business", "link": "https://facebook.com/alpha",
         "fan_count": 500, "tasks": ["MANAGE", "CREATE_CONTENT"], "access_token": "PAGE_TOKEN_1"}
PAGE2 = {"id": "222", "name": "Beta Page", "category": "Brand", "link": "https://facebook.com/beta",
         "fan_count": 50, "tasks": ["ANALYZE"], "access_token": "PAGE_TOKEN_2"}

def test_get_me_and_pages_with_paging():
    s = FakeSession([
        FakeResp(200, {"id": "999", "name": "Test User"}),
        FakeResp(200, {"data": [PAGE1], "paging": {"next": "https://graph.facebook.com/v21.0/me/accounts?after=x"}}),
        FakeResp(200, {"data": [PAGE2]}),
    ])
    c = MetaAPIClient("USER_TOKEN", session=s, backoff_seconds=0)
    assert c.get_me()["name"] == "Test User"
    pages = c.get_my_pages()
    assert [p["id"] for p in pages] == ["111", "222"]

def test_error_mapping_expired_and_permission():
    s = FakeSession([FakeResp(400, {"error": {"code": 190, "message": "Session expired"}})])
    with pytest.raises(TokenExpiredError): MetaAPIClient("T", session=s, backoff_seconds=0).get_me()
    s2 = FakeSession([FakeResp(403, {"error": {"code": 200, "message": "Requires pages_show_list"}})])
    with pytest.raises(PermissionMissingError): MetaAPIClient("T", session=s2, backoff_seconds=0).get_my_pages()

def test_rate_limit_retries_then_succeeds():
    err = FakeResp(400, {"error": {"code": 4, "message": "Too many calls"}})
    ok = FakeResp(200, {"id": "1", "name": "U"})
    s = FakeSession([err, err, ok])
    c = MetaAPIClient("T", session=s, backoff_seconds=0, max_retries=3)
    assert c.get_me()["id"] == "1" and len(s.calls) == 3

def test_token_never_in_error_message():
    s = FakeSession([FakeResp(400, {"error": {"code": 190, "message": "bad token SECRET_TOKEN_HERE"}})])
    c = MetaAPIClient("SECRET_TOKEN_HERE", session=s, backoff_seconds=0)
    with pytest.raises(TokenExpiredError) as e: c.get_me()
    assert "SECRET_TOKEN_HERE" not in str(e.value) or "***TOKEN***" in str(e.value)

def test_oauth_url_and_state():
    url, state = oauth.build_oauth_url("12345", "http://127.0.0.1:5555/oauth/callback")
    assert "client_id=12345" in url and "response_type=code" in url and "pages_show_list" in url
    assert oauth.verify_state(state, state) and not oauth.verify_state("evil", state)

def test_callback_server_captures_code():
    server, result, redirect = oauth.start_callback_server()
    port = server.server_address[1]
    th = threading.Thread(target=server.handle_request); th.start()
    urllib.request.urlopen(f"http://127.0.0.1:{port}/oauth/callback?code=CODE123&state=abc", timeout=5).read()
    th.join(timeout=5); server.server_close()
    assert result.code == "CODE123" and result.state == "abc"

def test_token_store_encrypted_and_masked(tmp_path):
    ts = TokenStore(str(tmp_path / "t.enc"), str(tmp_path / "t.key"))
    ts.set_token("profile:1", "EAABwzLixnj0SECRET")
    assert ts.get_token("profile:1") == "EAABwzLixnj0SECRET"
    raw = open(tmp_path / "t.enc", "rb").read()
    assert b"SECRET" not in raw  # encrypted at rest
    assert TokenStore.mask("EAABwzLixnj0SECRET").endswith("CRET") and "…" in TokenStore.mask("EAABwzLixnj0SECRET")
    ts.delete_token("profile:1"); assert ts.get_token("profile:1") is None

class StubClient:
    def __init__(self, pages=None, exc=None): self.pages = pages or []; self.exc = exc
    def get_my_pages(self):
        if self.exc: raise self.exc
        return self.pages

@pytest.fixture()
def db(tmp_path):
    d = DBManager(str(tmp_path / "s.db")); yield d; d.close()

def test_sync_creates_links_and_dedupes(db):
    pid = db.add_profile("Sync User", facebook_user_id="999")
    r1 = sync_profile_pages(db, pid, StubClient([PAGE1, PAGE2]))
    assert r1["ok"] and r1["pages_processed"] == 2 and len(db.list_pages()) == 2
    r2 = sync_profile_pages(db, pid, StubClient([PAGE1, PAGE2]))  # re-sync: no duplicates
    assert len(db.list_pages()) == 2
    rows = {r["facebook_page_id"]: r for r in db.list_pages()}
    assert rows["111"]["profiles"] == "Sync User" and rows["111"]["follower_count"] == 500
    prof = db.list_profiles()[0]
    assert prof["connection_status"] == "Connected" and prof["last_sync_at"]
    assert db.list_sync_logs()[0]["result"] == "Success"

def test_sync_flags_missing_not_deleted(db):
    pid = db.add_profile("Sync User")
    sync_profile_pages(db, pid, StubClient([PAGE1, PAGE2]))
    r = sync_profile_pages(db, pid, StubClient([PAGE1]))
    assert r["missing_flagged"] and len(db.list_pages()) == 2
    rows = {x["facebook_page_id"]: x for x in db.list_pages()}
    assert rows["222"]["manual_status"] == "Missing - Verify"

def test_sync_token_expired_updates_profile(db):
    pid = db.add_profile("Exp User")
    r = sync_profile_pages(db, pid, StubClient(exc=TokenExpiredError("expired", 190)))
    assert not r["ok"]
    prof = db.list_profiles()[0]
    assert prof["authorization_status"] == "Token Expired"
    assert db.list_sync_logs()[0]["result"] == "Failed"

def test_tasks_to_role():
    assert tasks_to_role(["MANAGE"]) == "Admin (Manage)"
    assert tasks_to_role(["ANALYZE"]) == "Analyst"
    assert tasks_to_role(None) == "Unknown"

def test_server_meta_exchange_uses_env_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("META_APP_ID", "12345"); monkeypatch.setenv("META_APP_SECRET", "server-only-secret")
    from licensing_server.meta_exchange import exchange_code
    calls = []
    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        class R:
            def json(self):
                if params.get("grant_type") == "fb_exchange_token":
                    return {"access_token": "LONG_TOKEN", "expires_in": 5184000}
                return {"access_token": "SHORT_TOKEN", "expires_in": 3600}
        return R()
    out = exchange_code("CODE", "http://127.0.0.1:1/oauth/callback", http_get=fake_get)
    assert out["access_token"] == "LONG_TOKEN"
    assert calls[0]["client_secret"] == "server-only-secret"  # secret used server-side only

def test_server_meta_exchange_missing_config(monkeypatch):
    monkeypatch.delenv("META_APP_ID", raising=False); monkeypatch.delenv("META_APP_SECRET", raising=False)
    from licensing_server.meta_exchange import exchange_code
    with pytest.raises(RuntimeError): exchange_code("C", "http://x")
