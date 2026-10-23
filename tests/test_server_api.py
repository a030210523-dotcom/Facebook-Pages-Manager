import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_fastapi_licensing_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("FPM_SIGNING_SECRET", "test-secret")
    monkeypatch.setenv("FPM_ADMIN_TOKEN", "test-admin")
    monkeypatch.setenv("FPM_LICENSE_DB", str(tmp_path / "api.db"))
    from fastapi.testclient import TestClient
    from licensing_server.main import app
    c = TestClient(app)
    assert c.get("/health").json()["status"] == "ok"
    assert c.get("/api/admin/licenses").status_code == 403  # server-side RBAC
    r = c.post("/api/admin/licenses", json={"customer_name": "API Cust", "license_type": "30 days", "max_devices": 1},
               headers={"x-admin-token": "test-admin"})
    assert r.status_code == 200
    key = r.json()["license_key"]
    assert c.post("/api/license/activate", json={"license_key": key, "installation_id": "pc-1"}).status_code == 200
    assert c.post("/api/license/validate", json={"license_key": key, "installation_id": "pc-9"}).status_code == 400
    assert c.post("/api/license/validate", json={"license_key": key, "installation_id": "pc-1"}).status_code == 200
    listed = c.get("/api/admin/licenses", headers={"x-admin-token": "test-admin"}).json()
    assert key not in str(listed) and listed[0]["key_last4"] == key[-4:]
