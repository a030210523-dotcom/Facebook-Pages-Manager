"""Local-server fallback: with the compiled default https://localhost:8000 the
desktop must still reach a plain local owner server at http://127.0.0.1:8000."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pytest
import requests
from fastapi.testclient import TestClient
from desktop.services.licensing_client import LicensingClient, LicenseCache
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
    r = c.post("/api/admin/licenses", json={"customer_name": "Fallback Cust",
                                            "license_type": "30 days", "max_devices": 1},
               headers={"x-admin-token": "adm"})
    return c, r.json()["license_key"], pub


class LocalhostRefusingAdapter:
    """Simulates the owner's PC: https://localhost:8000 refuses the connection
    (nothing listens there / SSL mismatch), http://127.0.0.1:8000 answers."""
    def __init__(self, tc): self.tc = tc; self.seen = []
    def _path(self, url): return "/" + url.split("/", 3)[3]
    def post(self, url, json=None, timeout=None):
        self.seen.append(url)
        if url.startswith("https://"):
            raise requests.ConnectionError("Failed to establish a new connection: [WinError 10061]")
        return self.tc.post(self._path(url), json=json)
    def get(self, url, timeout=None):
        self.seen.append(url)
        if url.startswith("https://"):
            raise requests.ConnectionError("Failed to establish a new connection: [WinError 10061]")
        return self.tc.get(self._path(url))


def test_activation_falls_back_to_plain_local_server(tmp_path, server):
    tc, key, pub = server
    cache = LicenseCache(str(tmp_path / "lic.enc"), str(tmp_path / "lic.key"))
    adapter = LocalhostRefusingAdapter(tc)
    lc = LicensingClient("https://localhost:8000", cache, http=adapter, pinned_public_key=pub)
    payload = lc.activate(key, "install-fallback-1")
    assert payload["customer_name"] == "Fallback Cust"
    assert lc.server_url in ("http://localhost:8000", "http://127.0.0.1:8000")  # stuck to a working plain-local address
    assert adapter.seen[0].startswith("https://localhost:8000")  # default tried first
    assert lc.current_status()["licensed"]


def test_no_fallback_for_remote_urls(tmp_path, server):
    tc, key, pub = server
    cache = LicenseCache(str(tmp_path / "lic.enc"), str(tmp_path / "lic.key"))
    class DeadAdapter:
        def post(self, url, json=None, timeout=None): raise requests.ConnectionError("dead")
        def get(self, url, timeout=None): raise requests.ConnectionError("dead")
    lc = LicensingClient("https://license.example.com", cache, http=DeadAdapter(),
                         pinned_public_key=pub)
    assert lc._candidate_urls() == ["https://license.example.com"]
    with pytest.raises(requests.ConnectionError):
        lc.activate(key, "install-x")
