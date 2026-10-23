"""Licensing core (Sections 16-23). Server-authoritative, pure logic — reusable & testable.
Keys are stored HASHED (sha256). Full key is shown once at generation, via authorized workflow only.
Signed responses use HMAC-SHA256 with a SERVER-ONLY secret (env FPM_SIGNING_SECRET, never in desktop app).
Production DB: PostgreSQL via SQLAlchemy in main.py deployment; this core uses SQLite for dev/tests
with the same schema/logic so behaviour is identical and verifiable."""
import hashlib, hmac, json, secrets, sqlite3, os, threading
from datetime import datetime, timezone, timedelta

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # unambiguous
LICENSE_DAYS = {"Trial": 14, "30 days": 30, "90 days": 90, "180 days": 180, "1 year": 365, "Lifetime": None}

def now(): return datetime.now(timezone.utc)
def iso(dt): return dt.isoformat(timespec="seconds")

def generate_key() -> str:
    groups = ["".join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(4)]
    return "FPM-" + "-".join(groups)

def hash_key(key: str) -> str:
    return hashlib.sha256(key.strip().upper().encode()).hexdigest()

def sign_payload(payload: dict, secret: str) -> str:
    msg = json.dumps(payload, sort_keys=True).encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()

def verify_signed(payload: dict, signature: str, secret: str) -> bool:
    return hmac.compare_digest(sign_payload(payload, secret), signature or "")

class LicenseStore:
    def __init__(self, db_path, signing_secret=None, ed25519_private_key_b64=None):
        if not signing_secret and not ed25519_private_key_b64:
            raise ValueError("A signing method is required: Ed25519 private key (production) or HMAC secret (dev only)")
        self.signing_secret = signing_secret
        self.ed25519_private_key_b64 = ed25519_private_key_b64
        self.conn = sqlite3.connect(db_path, check_same_thread=False); self.conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS licenses(
          id INTEGER PRIMARY KEY AUTOINCREMENT, key_hash TEXT UNIQUE NOT NULL, key_last4 TEXT,
          customer_name TEXT NOT NULL, customer_email TEXT, customer_phone TEXT,
          license_type TEXT NOT NULL, issued_at TEXT, expiry_date TEXT,
          max_devices INTEGER DEFAULT 1, status TEXT DEFAULT 'Pending Activation', notes TEXT);
        CREATE TABLE IF NOT EXISTS activations(
          id INTEGER PRIMARY KEY AUTOINCREMENT, license_id INTEGER NOT NULL,
          installation_id TEXT NOT NULL, device_label TEXT, activated_at TEXT,
          last_validated_at TEXT, app_version TEXT, status TEXT DEFAULT 'Active',
          UNIQUE(license_id, installation_id));
        CREATE TABLE IF NOT EXISTS audit_logs(
          id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT, action TEXT, details TEXT, created_at TEXT);
        """); self.conn.commit()

    def audit(self, actor, action, details=None):
        self.conn.execute("INSERT INTO audit_logs(actor,action,details,created_at) VALUES(?,?,?,?)",
                          (actor, action, details, iso(now()))); self.conn.commit()

    def create_license(self, actor, customer_name, license_type="30 days", max_devices=1,
                       email=None, phone=None, custom_expiry=None, notes=None):
        if license_type not in LICENSE_DAYS and not custom_expiry: raise ValueError("Unknown license type")
        key = generate_key(); kh = hash_key(key)
        issued = now()
        expiry = custom_expiry or (None if LICENSE_DAYS[license_type] is None else iso(issued + timedelta(days=LICENSE_DAYS[license_type])))
        cur = self.conn.execute(
            "INSERT INTO licenses(key_hash,key_last4,customer_name,customer_email,customer_phone,license_type,issued_at,expiry_date,max_devices,notes) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (kh, key[-4:], customer_name, email, phone, license_type, iso(issued), expiry, max_devices, notes))
        self.conn.commit(); self.audit(actor, "license_created", f"id={cur.lastrowid} type={license_type}")
        return {"id": cur.lastrowid, "license_key": key, "expiry_date": expiry}  # key revealed ONCE here

    def _find(self, key):
        return self.conn.execute("SELECT * FROM licenses WHERE key_hash=?", (hash_key(key),)).fetchone()

    def _check_usable(self, lic):
        if lic is None: return "License key not found"
        if lic["status"] == "Revoked": return "License has been revoked"
        if lic["status"] == "Suspended": return "License has been suspended"
        if lic["expiry_date"] and datetime.fromisoformat(lic["expiry_date"]) < now():
            self.conn.execute("UPDATE licenses SET status='Expired' WHERE id=?", (lic["id"],)); self.conn.commit()
            return "License has expired"
        return None

    def activate(self, key, installation_id, device_label=None, app_version=None, actor="customer"):
        lic = self._find(key); err = self._check_usable(lic)
        if err: return {"ok": False, "error": err}
        existing = self.conn.execute("SELECT * FROM activations WHERE license_id=? AND installation_id=?",
                                     (lic["id"], installation_id)).fetchone()
        if not existing:
            active = self.conn.execute("SELECT COUNT(*) c FROM activations WHERE license_id=? AND status='Active'",
                                       (lic["id"],)).fetchone()["c"]
            if active >= lic["max_devices"]:
                return {"ok": False, "error": "Activation Limit Reached"}
            self.conn.execute("INSERT INTO activations(license_id,installation_id,device_label,activated_at,last_validated_at,app_version) VALUES(?,?,?,?,?,?)",
                              (lic["id"], installation_id, device_label, iso(now()), iso(now()), app_version))
        else:
            self.conn.execute("UPDATE activations SET status='Active',last_validated_at=? WHERE id=?", (iso(now()), existing["id"]))
        self.conn.execute("UPDATE licenses SET status='Active' WHERE id=?", (lic["id"],)); self.conn.commit()
        self.audit(actor, "license_activated", f"license_id={lic['id']}")
        return {"ok": True, "signed": self._signed_response(lic)}

    def _signed_response(self, lic):
        payload = {"license_id": lic["id"], "customer_name": lic["customer_name"],
                   "license_type": lic["license_type"], "expiry_date": lic["expiry_date"],
                   "max_devices": lic["max_devices"], "status": "Active", "validated_at": iso(now())}
        if self.ed25519_private_key_b64:
            from .signing import sign_payload_ed
            return {"payload": payload, "signature": sign_payload_ed(payload, self.ed25519_private_key_b64),
                    "alg": "ed25519"}
        return {"payload": payload, "signature": sign_payload(payload, self.signing_secret), "alg": "hmac-sha256"}

    def validate(self, key, installation_id):
        lic = self._find(key); err = self._check_usable(lic)
        if err: return {"ok": False, "error": err}
        act = self.conn.execute("SELECT * FROM activations WHERE license_id=? AND installation_id=? AND status='Active'",
                                (lic["id"], installation_id)).fetchone()
        if not act: return {"ok": False, "error": "Device not activated"}
        self.conn.execute("UPDATE activations SET last_validated_at=? WHERE id=?", (iso(now()), act["id"])); self.conn.commit()
        return {"ok": True, "signed": self._signed_response(lic)}

    def _set_status(self, actor, license_id, status, action):
        self.conn.execute("UPDATE licenses SET status=? WHERE id=?", (status, license_id)); self.conn.commit()
        self.audit(actor, action, f"license_id={license_id}")

    def suspend(self, actor, lid): self._set_status(actor, lid, "Suspended", "license_suspended")
    def revoke(self, actor, lid): self._set_status(actor, lid, "Revoked", "license_revoked")
    def renew(self, actor, lid, extra_days):
        lic = self.conn.execute("SELECT * FROM licenses WHERE id=?", (lid,)).fetchone()
        base = datetime.fromisoformat(lic["expiry_date"]) if lic["expiry_date"] and datetime.fromisoformat(lic["expiry_date"]) > now() else now()
        new_exp = iso(base + timedelta(days=extra_days))
        self.conn.execute("UPDATE licenses SET expiry_date=?,status='Active' WHERE id=?", (new_exp, lid)); self.conn.commit()
        self.audit(actor, "license_renewed", f"license_id={lid} new_expiry={new_exp}"); return new_exp
    def deactivate_device(self, actor, activation_id):
        self.conn.execute("UPDATE activations SET status='Deactivated' WHERE id=?", (activation_id,)); self.conn.commit()
        self.audit(actor, "device_deactivated", f"activation_id={activation_id}")
    def list_licenses(self, status=None, search=None):
        q = "SELECT id,customer_name,customer_email,license_type,issued_at,expiry_date,max_devices,status,key_last4 FROM licenses WHERE 1=1"; a=[]
        if status: q += " AND status=?"; a.append(status)
        if search: q += " AND (customer_name LIKE ? OR customer_email LIKE ?)"; a += [f"%{search}%"]*2
        return [dict(r) for r in self.conn.execute(q + " ORDER BY id DESC", a)]  # keys masked: last4 only
    def stats(self):
        c = self.conn; s = lambda q: c.execute(q).fetchone()["x"]
        return {"total": s("SELECT COUNT(*) x FROM licenses"), "active": s("SELECT COUNT(*) x FROM licenses WHERE status='Active'"),
                "pending": s("SELECT COUNT(*) x FROM licenses WHERE status='Pending Activation'"),
                "expired": s("SELECT COUNT(*) x FROM licenses WHERE status='Expired'"),
                "suspended": s("SELECT COUNT(*) x FROM licenses WHERE status='Suspended'"),
                "revoked": s("SELECT COUNT(*) x FROM licenses WHERE status='Revoked'"),
                "activations": s("SELECT COUNT(*) x FROM activations WHERE status='Active'")}

def check_offline_grace(signed, secret=None, grace_days=7, at=None, public_key_b64=None):
    """Verify cached signed license offline (Section 21). Unverified file = invalid.
    Ed25519 licenses verify with the server PUBLIC key (safe on desktop);
    HMAC is dev-only and needs the secret."""
    if not signed: return {"ok": False, "error": "No cached license"}
    if signed.get("alg") == "ed25519":
        from .signing import verify_payload_ed
        if not public_key_b64 or not verify_payload_ed(signed.get("payload", {}), signed.get("signature", ""), public_key_b64):
            return {"ok": False, "error": "Invalid cached license signature"}
    elif not secret or not verify_signed(signed.get("payload", {}), signed.get("signature", ""), secret):
        return {"ok": False, "error": "Invalid cached license signature"}
    p = signed["payload"]; at = at or now()
    validated = datetime.fromisoformat(p["validated_at"])
    if p.get("expiry_date") and datetime.fromisoformat(p["expiry_date"]) < at:
        return {"ok": False, "error": "License expired"}
    if (at - validated).days > grace_days:
        return {"ok": False, "error": "Offline grace period expired — internet validation required"}
    return {"ok": True, "payload": p, "offline": True}
