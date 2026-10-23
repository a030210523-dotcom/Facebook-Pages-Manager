import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import timedelta
import pytest
from licensing_server.core import LicenseStore, generate_key, check_offline_grace, verify_signed, now

SECRET = "test-server-secret-not-in-desktop-app"

@pytest.fixture()
def store(tmp_path):
    return LicenseStore(str(tmp_path / "lic.db"), SECRET)

def test_key_format():
    k = generate_key(); parts = k.split("-")
    assert parts[0] == "FPM" and len(parts) == 5 and all(len(p) == 4 for p in parts[1:])
    assert generate_key() != generate_key()

def test_activation_valid_and_signed(store):
    lic = store.create_license("Super Admin", "Customer A", "30 days", max_devices=1)
    r = store.activate(lic["license_key"], "install-1", "PC-1")
    assert r["ok"] and verify_signed(r["signed"]["payload"], r["signed"]["signature"], SECRET)
    v = store.validate(lic["license_key"], "install-1"); assert v["ok"]

def test_invalid_key(store):
    assert store.activate("FPM-XXXX-XXXX-XXXX-XXXX", "i1")["ok"] is False

def test_device_limit(store):
    lic = store.create_license("Super Admin", "Customer B", "90 days", max_devices=1)
    assert store.activate(lic["license_key"], "dev-1")["ok"]
    r = store.activate(lic["license_key"], "dev-2")
    assert not r["ok"] and "Limit" in r["error"]
    # deactivate first device, then second can activate
    aid = store.conn.execute("SELECT id FROM activations WHERE status='Active'").fetchone()["id"]
    store.deactivate_device("Super Admin", aid)
    assert store.activate(lic["license_key"], "dev-2")["ok"]

def test_suspend_revoke_renew(store):
    lic = store.create_license("Super Admin", "Customer C", "30 days")
    store.suspend("Super Admin", lic["id"])
    assert not store.activate(lic["license_key"], "i1")["ok"]
    store.renew("Super Admin", lic["id"], 30)
    assert store.activate(lic["license_key"], "i1")["ok"]
    store.revoke("Super Admin", lic["id"])
    assert not store.validate(lic["license_key"], "i1")["ok"]

def test_expired_license(store):
    lic = store.create_license("Super Admin", "Old", "Trial", custom_expiry="2000-01-01T00:00:00+00:00")
    r = store.activate(lic["license_key"], "i1")
    assert not r["ok"] and "expired" in r["error"].lower()

def test_keys_masked_in_listing(store):
    lic = store.create_license("Super Admin", "Mask Me", "30 days")
    listed = store.list_licenses()
    assert listed[0]["key_last4"] == lic["license_key"][-4:]
    assert "key_hash" not in listed[0] and lic["license_key"] not in str(listed)

def test_offline_grace_and_tamper(store):
    lic = store.create_license("Super Admin", "Offline", "1 year")
    signed = store.activate(lic["license_key"], "i1")["signed"]
    assert check_offline_grace(signed, SECRET, grace_days=7)["ok"]
    tampered = {"payload": {**signed["payload"], "customer_name": "Hacker"}, "signature": signed["signature"]}
    assert not check_offline_grace(tampered, SECRET)["ok"]
    old = {"payload": {**signed["payload"]}, "signature": signed["signature"]}
    # grace exceeded: simulate by checking 30 days later with a re-signed old payload
    from licensing_server.core import sign_payload
    p = {**signed["payload"], "validated_at": (now() - timedelta(days=30)).isoformat(timespec="seconds")}
    stale = {"payload": p, "signature": sign_payload(p, SECRET)}
    assert not check_offline_grace(stale, SECRET, grace_days=7)["ok"]

def test_admin_stats(store):
    store.create_license("Super Admin", "S1", "30 days"); store.create_license("Super Admin", "S2", "Trial")
    s = store.stats(); assert s["total"] == 2 and s["pending"] == 2
