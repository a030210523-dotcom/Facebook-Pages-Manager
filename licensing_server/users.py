"""Server user accounts, Argon2id password hashing, sessions & login rate limiting
(Sections 15/23, Phase 4). Roles: Super Admin > Admin > Licensed User.
RBAC is enforced here on the server — never by hiding buttons in the desktop UI.
Failed logins are counted; 5 failures lock the account for 15 minutes (documented policy)."""
import hashlib, secrets, sqlite3
from datetime import datetime, timezone, timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()  # Argon2id defaults
MAX_FAILURES = 5; LOCK_MINUTES = 15; SESSION_HOURS = 12

def _now(): return datetime.now(timezone.utc)
def _iso(dt): return dt.isoformat(timespec="seconds")

class UserStore:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS server_users(
          id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'Licensed User',
          is_active INTEGER DEFAULT 1, failed_attempts INTEGER DEFAULT 0,
          locked_until TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS sessions(
          token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires_at TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS user_audit(
          id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT, action TEXT, details TEXT, created_at TEXT);
        """); self.conn.commit()

    def audit(self, actor, action, details=None):
        self.conn.execute("INSERT INTO user_audit(actor,action,details,created_at) VALUES(?,?,?,?)",
                          (actor, action, details, _iso(_now()))); self.conn.commit()

    def create_user(self, actor, username, password, role="Licensed User"):
        if role not in ("Super Admin", "Admin", "Licensed User"): raise ValueError("Invalid role")
        if len(password) < 10: raise ValueError("Password must be at least 10 characters")
        try:
            cur = self.conn.execute(
                "INSERT INTO server_users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                (username, _ph.hash(password), role, _iso(_now())))
            self.conn.commit()
        except sqlite3.IntegrityError: raise ValueError(f"User {username} already exists")
        self.audit(actor, "user_created", f"user={username} role={role}")
        return cur.lastrowid

    def bootstrap_super_admin(self, username, password):
        """One-time server-side bootstrap: only works when NO Super Admin exists yet (Section 15/23)."""
        if self.conn.execute("SELECT 1 FROM server_users WHERE role='Super Admin'").fetchone():
            raise PermissionError("Super Admin already exists — bootstrap is closed")
        return self.create_user("bootstrap", username, password, role="Super Admin")

    def login(self, username, password):
        r = self.conn.execute("SELECT * FROM server_users WHERE username=?", (username,)).fetchone()
        if not r or not r["is_active"]:
            self.audit(username, "login_failed", "unknown or inactive user"); return None
        if r["locked_until"] and datetime.fromisoformat(r["locked_until"]) > _now():
            self.audit(username, "login_blocked_locked", None); return None
        try:
            _ph.verify(r["password_hash"], password)
        except VerifyMismatchError:
            fails = r["failed_attempts"] + 1
            lock = _iso(_now() + timedelta(minutes=LOCK_MINUTES)) if fails >= MAX_FAILURES else None
            self.conn.execute("UPDATE server_users SET failed_attempts=?,locked_until=? WHERE id=?",
                              (fails, lock, r["id"])); self.conn.commit()
            self.audit(username, "login_failed", f"attempts={fails}" + (" LOCKED" if lock else ""))
            return None
        self.conn.execute("UPDATE server_users SET failed_attempts=0,locked_until=NULL WHERE id=?", (r["id"],))
        token = secrets.token_urlsafe(32)
        th = hashlib.sha256(token.encode()).hexdigest()
        self.conn.execute("INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",
                          (th, r["id"], _iso(_now() + timedelta(hours=SESSION_HOURS)), _iso(_now())))
        self.conn.commit(); self.audit(username, "login_success", None)
        return {"token": token, "username": username, "role": r["role"]}

    def user_for_token(self, token):
        if not token: return None
        th = hashlib.sha256(token.encode()).hexdigest()
        r = self.conn.execute(
            """SELECT u.* FROM sessions s JOIN server_users u ON u.id=s.user_id
               WHERE s.token_hash=? AND s.expires_at>? AND u.is_active=1""",
            (th, _iso(_now()))).fetchone()
        return dict(r) if r else None

    def set_role(self, actor, username, new_role):
        caller = self.conn.execute("SELECT * FROM server_users WHERE username=?", (actor,)).fetchone()
        if not caller or caller["role"] != "Super Admin":
            raise PermissionError("Only Super Admin can change roles")
        if new_role not in ("Super Admin", "Admin", "Licensed User"): raise ValueError("Invalid role")
        self.conn.execute("UPDATE server_users SET role=? WHERE username=?", (new_role, username))
        self.conn.commit(); self.audit(actor, "role_changed", f"user={username} role={new_role}")

    def deactivate_user(self, actor, username):
        caller = self.conn.execute("SELECT * FROM server_users WHERE username=?", (actor,)).fetchone()
        if not caller or caller["role"] != "Super Admin":
            raise PermissionError("Only Super Admin can deactivate users")
        self.conn.execute("UPDATE server_users SET is_active=0 WHERE username=?", (username,))
        self.conn.commit(); self.audit(actor, "user_deactivated", f"user={username}")
