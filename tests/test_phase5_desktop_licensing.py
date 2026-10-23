import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
from fastapi.testclient import TestClient
from desktop.services.licensing_client import LicensingClient, LicenseCache, get_or_create_installation_id
from desktop.database.db_manager import DBManager
from licensing_server.signing import generate_keypair

@pytest.fixture()
def server(tmp_path, monkeypatch):
    priv, pub = generate_keypair()
    monkeypatch.setenv("FPM_ED25519_PRIVATE_KEY", priv)
    monkeypatch.setenv("FPM_ADMIN_TOKEN", "adm")
    monkeypatch.setenv("FPM_LICENSE_DB", str(tmp_path / "srv.db"))
    monkeypatch.delenv("FPM_SIGNING_SECRET", raising=False)
    from licensing_server.main import app
    c = TestClient(app)
    r = c.post("/api/admin/licenses", json={"customer_name": "Desktop Cust", "license_type": "30 days",
                                            "max_devices": 1}, headers={"x-admin-token": "adm"})
    return c, r.json()["license_key"], pub

class ClientAdapter:
    """Adapts FastAPI TestClient to the requests-style API the desktop client uses."""
    def __init__(self, tc): self.tc = tc
    def post(self, url, json=None, timeout=None):
        path = "/" + url.split("/", 3)[3]
        return self.tc.post(path, json=json)
    def get(self, url, timeout=None):
        path = "/" + url.split("/", 3)[3]
        return self.tc.get(path)

@pytest.fixture()
def client(tmp_path, server):
    tc, key, pub = server
    cache = LicenseCache(str(tmp_path / "lic.enc"), str(tmp_path / "lic.key"))
    return LicensingClient("http://testserver", cache, http=ClientAdapter(tc),
                           pinned_public_key=pub), key

def test_public_key_endpoint(server):
    tc, key, pub = server
    r = tc.get("/api/license/public-key")
    assert r.json()["alg"] == "ed25519" and r.json()["public_key"] == pub

def test_desktop_activation_and_offline_status(client):
    lc, key = client
    payload = lc.activate(key, "install-uuid-1", device_label="PC")
    assert payload["customer_name"] == "Desktop Cust"
    st = lc.current_status()
    assert st["licensed"] and st["status"] in ("Active", "Active (Offline Grace)")
    # cache file must not contain the signed payload in plain text
    raw = open(lc.cache.path, "rb").read()
    assert b"Desktop Cust" not in raw

def test_desktop_rejects_tampered_cache(client):
    lc, key = client
    lc.activate(key, "install-uuid-1")
    data = lc.cache.load()
    data["signed"]["payload"]["customer_name"] = "Free Rider"
    lc.cache.save(data)
    st = lc.current_status()
    assert not st["licensed"] and st["status"] == "Invalid"

def test_desktop_validate_online(client):
    lc, key = client
    lc.activate(key, "install-uuid-9")
    payload = lc.validate_online(key, "install-uuid-9")
    assert payload["license_id"] >= 1
    with pytest.raises(RuntimeError): lc.validate_online(key, "some-other-device")

def test_no_license_status(tmp_path):
    cache = LicenseCache(str(tmp_path / "x.enc"), str(tmp_path / "x.key"))
    lc = LicensingClient("http://testserver", cache, http=ClientAdapter(None))
    st = lc.current_status()
    assert not st["licensed"] and st["status"] == "Not Activated"

def test_installation_id_stable(tmp_path):
    db = DBManager(str(tmp_path / "app.db"))
    a = get_or_create_installation_id(db); b = get_or_create_installation_id(db)
    assert a == b and len(a) >= 32
    db.close()
