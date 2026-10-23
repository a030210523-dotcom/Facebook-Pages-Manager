import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from licensing_server.users import UserStore

@pytest.fixture()
def users(tmp_path):
    return UserStore(str(tmp_path / "u.db"))

def test_bootstrap_only_once(users):
    users.bootstrap_super_admin("aamir", "OwnerPass!123")
    with pytest.raises(PermissionError): users.bootstrap_super_admin("intruder", "IntruderPass!1")

def test_argon2_login_and_session(users):
    users.bootstrap_super_admin("aamir", "OwnerPass!123")
    r = users.login("aamir", "OwnerPass!123")
    assert r and r["role"] == "Super Admin"
    assert users.user_for_token(r["token"])["username"] == "aamir"
    assert users.login("aamir", "wrong-password") is None
    stored = users.conn.execute("SELECT password_hash FROM server_users WHERE username='aamir'").fetchone()[0]
    assert stored.startswith("$argon2id$") and "OwnerPass" not in stored

def test_lockout_after_5_failures(users):
    users.bootstrap_super_admin("boss", "BossPass!1234")
    for _ in range(5): assert users.login("boss", "nope-nope") is None
    # Even the CORRECT password is refused while locked (rate limiting policy)
    assert users.login("boss", "BossPass!1234") is None

def test_only_super_admin_changes_roles(users):
    users.bootstrap_super_admin("aamir", "OwnerPass!123")
    users.create_user("aamir", "helper", "HelperPass!1", role="Admin")
    with pytest.raises(PermissionError): users.set_role("helper", "helper", "Super Admin")
    users.set_role("aamir", "helper", "Licensed User")
    row = users.conn.execute("SELECT role FROM server_users WHERE username='helper'").fetchone()
    assert row["role"] == "Licensed User"

def test_short_password_rejected(users):
    with pytest.raises(ValueError): users.create_user("root", "x", "short")

def test_api_login_and_rbac(tmp_path, monkeypatch):
    monkeypatch.setenv("FPM_SIGNING_SECRET", "s"); monkeypatch.setenv("FPM_ADMIN_TOKEN", "adm")
    monkeypatch.setenv("FPM_LICENSE_DB", str(tmp_path / "api.db"))
    from fastapi.testclient import TestClient
    from licensing_server.main import app
    c = TestClient(app)
    r = c.post("/api/auth/bootstrap-super-admin", json={"username": "aamir", "password": "OwnerPass!123"},
               headers={"x-admin-token": "adm"})
    assert r.status_code == 200
    assert c.post("/api/auth/bootstrap-super-admin", json={"username": "x", "password": "Xpassword!123"},
                  headers={"x-admin-token": "adm"}).status_code == 409  # bootstrap closed
    login = c.post("/api/auth/login", json={"username": "aamir", "password": "OwnerPass!123"})
    assert login.status_code == 200
    token = login.json()["token"]
    # Super Admin session can create licenses without the bootstrap token
    r2 = c.post("/api/admin/licenses", json={"customer_name": "Session Cust"},
                headers={"authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    # No auth at all is still refused
    assert c.post("/api/admin/licenses", json={"customer_name": "Anon"}).status_code == 403
    assert c.post("/api/auth/login", json={"username": "aamir", "password": "bad"}).status_code == 401
