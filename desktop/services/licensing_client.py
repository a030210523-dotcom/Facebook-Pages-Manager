"""Desktop licensing client (Sections 17/20/21, Phase 5).

- Activation/validation talk to the licensing server over HTTP(S).
- The server returns an Ed25519-SIGNED license payload. The desktop verifies it with
  the server's PUBLIC key (fetched at activation, or pinned via env FPM_LICENSE_PUBLIC_KEY
  / config). The desktop never holds any server secret.
- The verified signed payload is cached ENCRYPTED on disk (Fernet, TokenStore mechanics).
- Offline: cached payload is accepted only within the grace period AND only if the
  signature verifies AND the license itself has not expired. Anything else = not licensed.
- Installation ID is a random UUID generated once — no hardware fingerprinting."""
import json, os, uuid
from datetime import datetime, timezone
from cryptography.fernet import Fernet

GRACE_DAYS_DEFAULT = 7

def _now(): return datetime.now(timezone.utc)

def get_or_create_installation_id(db):
    iid = db.get_setting("installation_id")
    if not iid:
        iid = str(uuid.uuid4()); db.set_setting("installation_id", iid)
    return iid

class LicenseCache:
    def __init__(self, cache_path, key_path):
        os.makedirs(os.path.dirname(os.path.abspath(cache_path)), exist_ok=True)
        if not os.path.exists(key_path):
            with open(key_path, "wb") as f: f.write(Fernet.generate_key())
            try: os.chmod(key_path, 0o600)
            except OSError: pass
        with open(key_path, "rb") as f: self._f = Fernet(f.read())
        self.path = cache_path
    def save(self, data):
        with open(self.path, "wb") as fh: fh.write(self._f.encrypt(json.dumps(data).encode()))
        try: os.chmod(self.path, 0o600)
        except OSError: pass
    def load(self):
        if not os.path.exists(self.path): return None
        try: return json.loads(self._f.decrypt(open(self.path, "rb").read()).decode())
        except Exception: return None  # tampered cache is treated as no license
    def clear(self):
        if os.path.exists(self.path): os.remove(self.path)

class LicensingClient:
    def __init__(self, server_url, cache, http=None, pinned_public_key=None):
        self.server_url = server_url.rstrip("/"); self.cache = cache
        self.pinned_public_key = pinned_public_key or os.environ.get("FPM_LICENSE_PUBLIC_KEY")
        if http is None:
            import requests; http = requests
        self.http = http

    def _candidate_urls(self):
        """Base URLs to try, in order. Local fallback: the app's compiled default is
        https://localhost:8000, but a locally-run owner server listens on plain
        http://127.0.0.1:8000 — when the configured local URL cannot be reached,
        the plain local address is tried automatically so activation still works
        when the app was launched directly (no launcher .bat / env var needed).
        Non-local (production) URLs are never rewritten."""
        urls = [self.server_url]
        u = self.server_url
        if "localhost" in u or "127.0.0.1" in u:
            variants = []
            if u.startswith("https://"):
                variants.append("http://" + u[len("https://"):])
            variants.append(u.replace("localhost", "127.0.0.1"))
            if u.startswith("https://"):
                variants.append("http://" + u[len("https://"):].replace("localhost", "127.0.0.1"))
            for v in variants:
                if v not in urls: urls.append(v)
        return urls

    def _post(self, path, payload):
        last = None
        for base in self._candidate_urls():
            try:
                r = self.http.post(f"{base}{path}", json=payload, timeout=20)
            except Exception as e:  # connection-level failure -> try next candidate
                last = e; continue
            self.server_url = base  # stick to the address that actually answered
            return r
        raise last if last else RuntimeError("Could not reach the licensing server")

    def _get(self, path):
        last = None
        for base in self._candidate_urls():
            try:
                r = self.http.get(f"{base}{path}", timeout=15)
            except Exception as e:
                last = e; continue
            self.server_url = base
            return r
        raise last if last else RuntimeError("Could not reach the licensing server")

    def fetch_public_key(self):
        r = self._get("/api/license/public-key")
        data = r.json()
        return data.get("public_key"), data.get("alg")

    def activate(self, license_key, installation_id, device_label=None, app_version=None):
        r = self._post("/api/license/activate", {
            "license_key": license_key, "installation_id": installation_id,
            "device_label": device_label, "app_version": app_version})
        data = r.json()
        if r.status_code != 200 or not data.get("ok"):
            raise RuntimeError(data.get("detail") or data.get("error") or f"Activation failed (HTTP {r.status_code})")
        signed = data["signed"]
        public_key = self.pinned_public_key
        if signed.get("alg") == "ed25519" and not public_key:
            public_key, _ = self.fetch_public_key()
        if not self._verify(signed, public_key):
            raise RuntimeError("Server license signature could not be verified — activation rejected.")
        self.cache.save({"signed": signed, "public_key": public_key, "license_key": license_key.strip(),
                         "license_key_last4": license_key.strip()[-4:], "saved_at": _now().isoformat()})
        return signed["payload"]

    def validate_online(self, license_key, installation_id):
        r = self._post("/api/license/validate", {
            "license_key": license_key, "installation_id": installation_id})
        data = r.json()
        if r.status_code != 200 or not data.get("ok"):
            raise RuntimeError(data.get("detail") or data.get("error") or f"Validation failed (HTTP {r.status_code})")
        signed = data["signed"]
        cached = self.cache.load() or {}
        public_key = self.pinned_public_key or cached.get("public_key")
        if signed.get("alg") == "ed25519" and not public_key:
            public_key, _ = self.fetch_public_key()
        if not self._verify(signed, public_key):
            raise RuntimeError("Server license signature could not be verified.")
        self.cache.save({"signed": signed, "public_key": public_key, "license_key": license_key.strip(),
                         "license_key_last4": (cached.get("license_key_last4") or license_key.strip()[-4:]),
                         "saved_at": _now().isoformat()})
        return signed["payload"]

    def _verify(self, signed, public_key):
        if signed.get("alg") == "ed25519":
            if not public_key: return False
            # Self-contained verifier: the desktop ships ONLY this public-key check,
            # never any server code or secret.
            import base64
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            try:
                pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key))
                pub.verify(base64.b64decode(signed["signature"]),
                           json.dumps(signed["payload"], sort_keys=True).encode())
                return True
            except Exception:
                return False
        # HMAC-signed licenses cannot be verified on the desktop (no secret) -> not trusted offline.
        return False

    def current_status(self, grace_days=GRACE_DAYS_DEFAULT):
        """Local status from the encrypted cache only. Never treats an unverified file as valid."""
        cached = self.cache.load()
        if not cached: return {"licensed": False, "status": "Not Activated",
                                "message": "No license found. Activate with a license key."}
        signed = cached.get("signed", {})
        if not self._verify(signed, cached.get("public_key")):
            return {"licensed": False, "status": "Invalid",
                    "message": "Cached license failed signature verification."}
        p = signed["payload"]
        if p.get("expiry_date") and datetime.fromisoformat(p["expiry_date"]) < _now():
            return {"licensed": False, "status": "Expired", "payload": p,
                    "message": "License has expired. Renew to continue using licensed features."}
        validated = datetime.fromisoformat(p["validated_at"])
        age_days = (_now() - validated).days
        if age_days > grace_days:
            return {"licensed": False, "status": "Online Validation Required", "payload": p,
                    "message": f"Offline grace period ({grace_days} days) ended. Connect to the internet to re-validate."}
        warn = None
        if p.get("expiry_date"):
            days_left = (datetime.fromisoformat(p["expiry_date"]) - _now()).days
            if days_left <= 7: warn = f"License expires in {days_left} day(s)."
        return {"licensed": True, "status": "Active (Offline Grace)" if age_days >= 1 else "Active",
                "payload": p, "message": warn or "License is valid.",
                "days_since_validation": age_days}
