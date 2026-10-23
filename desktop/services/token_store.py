"""Secure token storage (Sections 9/25). Tokens are encrypted at rest with Fernet
(cryptography). The encryption key lives in a separate key file created with
owner-only permissions (0600). Tokens are NEVER logged or displayed in full.
On Windows production, prefer the OS credential store (keyring/DPAPI) — this
encrypted-file store is the documented portable fallback."""
import json, os
from cryptography.fernet import Fernet

class TokenStore:
    def __init__(self, store_path, key_path):
        self.store_path = store_path; self.key_path = key_path
        os.makedirs(os.path.dirname(os.path.abspath(store_path)), exist_ok=True)
        if not os.path.exists(key_path):
            with open(key_path, "wb") as f: f.write(Fernet.generate_key())
            try: os.chmod(key_path, 0o600)
            except OSError: pass
        with open(key_path, "rb") as f: self._fernet = Fernet(f.read())

    def _load(self):
        if not os.path.exists(self.store_path): return {}
        try:
            with open(self.store_path, "rb") as f:
                raw = self._fernet.decrypt(f.read())
            return json.loads(raw.decode())
        except Exception:
            return {}  # corrupted/tampered store is treated as empty, never trusted

    def _save(self, data):
        blob = self._fernet.encrypt(json.dumps(data).encode())
        with open(self.store_path, "wb") as f: f.write(blob)
        try: os.chmod(self.store_path, 0o600)
        except OSError: pass

    def set_token(self, profile_key, token, kind="user"):
        data = self._load(); data[profile_key] = {"token": token, "kind": kind}; self._save(data)

    def get_token(self, profile_key):
        item = self._load().get(profile_key)
        return item["token"] if item else None

    def delete_token(self, profile_key):
        data = self._load(); data.pop(profile_key, None); self._save(data)

    @staticmethod
    def mask(token):
        if not token: return "(none)"
        return token[:4] + "…" + token[-4:] if len(token) > 10 else "****"
