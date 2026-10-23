"""Local SQLite database (Section 24). All local app data; no Facebook passwords, ever."""
import sqlite3, os
from datetime import datetime, timezone
from ..security.passwords import hash_password, verify_password

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles(
 id INTEGER PRIMARY KEY AUTOINCREMENT, facebook_user_id TEXT UNIQUE,
 display_name TEXT NOT NULL, profile_url TEXT, email TEXT, phone TEXT,
 email_source TEXT DEFAULT 'manual', phone_source TEXT DEFAULT 'manual',
 connection_status TEXT DEFAULT 'Not Connected', authorization_status TEXT DEFAULT 'Unknown',
 created_at TEXT, updated_at TEXT, last_sync_at TEXT, notes TEXT, is_active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS pages(
 id INTEGER PRIMARY KEY AUTOINCREMENT, facebook_page_id TEXT UNIQUE NOT NULL,
 page_name TEXT NOT NULL, page_url TEXT, category TEXT, follower_count INTEGER,
 created_at TEXT, updated_at TEXT, last_checked_at TEXT, notes TEXT,
 manual_status TEXT DEFAULT 'Unknown', data_source TEXT DEFAULT 'manual');
CREATE TABLE IF NOT EXISTS profile_page_access(
 id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER NOT NULL, page_id INTEGER NOT NULL,
 access_role TEXT, access_status TEXT DEFAULT 'Unknown', last_seen_at TEXT,
 UNIQUE(profile_id,page_id),
 FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
 FOREIGN KEY(page_id) REFERENCES pages(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS page_health_history(
 id INTEGER PRIMARY KEY AUTOINCREMENT, page_id INTEGER NOT NULL, checked_at TEXT,
 technical_connection_status TEXT DEFAULT 'Unknown', policy_status TEXT DEFAULT 'Unknown',
 restriction_status TEXT DEFAULT 'Unknown', error_details TEXT, data_source TEXT DEFAULT 'manual',
 FOREIGN KEY(page_id) REFERENCES pages(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS monetization_history(
 id INTEGER PRIMARY KEY AUTOINCREMENT, page_id INTEGER NOT NULL, checked_at TEXT,
 api_status TEXT DEFAULT 'Unknown', eligibility_status TEXT DEFAULT 'Unknown',
 available_products TEXT, restriction_details TEXT, data_source TEXT DEFAULT 'manual',
 manual_status TEXT DEFAULT 'Not Verified', notes TEXT,
 FOREIGN KEY(page_id) REFERENCES pages(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS sync_logs(
 id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER, started_at TEXT, finished_at TEXT,
 result TEXT, pages_processed INTEGER DEFAULT 0, error_message TEXT);
CREATE TABLE IF NOT EXISTS profile_invites(
 id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL,
 display_name TEXT, profile_link TEXT, note TEXT,
 status TEXT DEFAULT 'Pending', profile_id INTEGER,
 created_at TEXT, updated_at TEXT, accepted_at TEXT);
CREATE TABLE IF NOT EXISTS app_users(
 id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
 role TEXT NOT NULL DEFAULT 'Licensed User', is_active INTEGER DEFAULT 1, created_at TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS audit_logs(
 id INTEGER PRIMARY KEY AUTOINCREMENT, actor TEXT, action TEXT, details TEXT, created_at TEXT);
"""

class DuplicateError(ValueError):
    pass

class DBManager:
    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self): self.conn.close()

    # ---------- Profiles ----------
    def add_profile(self, display_name, facebook_user_id=None, profile_url=None, email=None,
                    phone=None, notes=None, connection_status="Not Connected"):
        if not display_name or not display_name.strip():
            raise ValueError("Display name is required")
        if facebook_user_id and self.conn.execute(
            "SELECT 1 FROM profiles WHERE facebook_user_id=?", (facebook_user_id,)).fetchone():
            raise DuplicateError(f"Profile with Facebook ID {facebook_user_id} already exists")
        t = now_iso()
        cur = self.conn.execute(
            """INSERT INTO profiles(display_name,facebook_user_id,profile_url,email,phone,notes,
               connection_status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)""",
            (display_name.strip(), facebook_user_id, profile_url, email, phone, notes, connection_status, t, t))
        self.conn.commit(); return cur.lastrowid

    def update_profile(self, pid, **fields):
        allowed = {"display_name","profile_url","email","phone","notes","connection_status",
                   "authorization_status","is_active","last_sync_at"}
        sets = {k:v for k,v in fields.items() if k in allowed}
        if not sets: return
        sets["updated_at"] = now_iso()
        self.conn.execute(f"UPDATE profiles SET {','.join(k+'=?' for k in sets)} WHERE id=?",
                          (*sets.values(), pid)); self.conn.commit()

    def delete_profile(self, pid):
        self.conn.execute("DELETE FROM profiles WHERE id=?", (pid,)); self.conn.commit()

    def list_profiles(self, search=None, active_only=False):
        q = "SELECT * FROM profiles WHERE 1=1"; args=[]
        if search:
            q += " AND (display_name LIKE ? OR facebook_user_id LIKE ? OR profile_url LIKE ?)"; args += [f"%{search}%"]*3
        if active_only: q += " AND is_active=1"
        q += " ORDER BY display_name"
        return [dict(r) for r in self.conn.execute(q, args)]

    # ---------- Profile invites (connect-by-link) ----------
    def add_invite(self, code, display_name=None, profile_link=None, note=None):
        if not code: raise ValueError("Invite code is required")
        if self.conn.execute("SELECT 1 FROM profile_invites WHERE code=?", (code,)).fetchone():
            raise DuplicateError("Invite code already exists")
        t = now_iso()
        cur = self.conn.execute(
            """INSERT INTO profile_invites(code,display_name,profile_link,note,status,created_at,updated_at)
               VALUES(?,?,?,?,'Pending',?,?)""",
            (code, display_name, profile_link, note, t, t))
        self.conn.commit(); return cur.lastrowid

    def list_invites(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM profile_invites ORDER BY id DESC")]

    def get_invite(self, iid):
        r = self.conn.execute("SELECT * FROM profile_invites WHERE id=?", (iid,)).fetchone()
        return dict(r) if r else None

    def update_invite(self, iid, **fields):
        allowed = {"display_name", "profile_link", "note", "status", "profile_id", "accepted_at"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets: return
        sets["updated_at"] = now_iso()
        self.conn.execute(f"UPDATE profile_invites SET {','.join(k + '=?' for k in sets)} WHERE id=?",
                          (*sets.values(), iid)); self.conn.commit()

    def delete_invite(self, iid):
        self.conn.execute("DELETE FROM profile_invites WHERE id=?", (iid,)); self.conn.commit()

    def profile_page_count(self, pid):
        return self.conn.execute("SELECT COUNT(*) c FROM profile_page_access WHERE profile_id=?", (pid,)).fetchone()["c"]

    def profile_details(self, pid):
        """Everything about ONE profile in one place (the app's core view):
        profile fields + every linked Page with the profile's access role, the
        Page's latest health and monetization status, and summary counts."""
        r = self.conn.execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone()
        if r is None: return None
        details = dict(r)
        rows = self.conn.execute(
            """SELECT p.*, a.access_role, a.access_status, a.last_seen_at AS access_last_seen_at
               FROM pages p JOIN profile_page_access a ON a.page_id=p.id
               WHERE a.profile_id=? ORDER BY p.page_name""", (pid,)).fetchall()
        pages = []
        followers = healthy = restricted = 0
        for row in rows:
            pg = dict(row)
            h = self.latest_health(pg["id"]); m = self.latest_monetization(pg["id"])
            pg["health_status"] = h["technical_connection_status"]
            pg["restriction_status"] = h["restriction_status"]
            pg["monetization_status"] = m["manual_status"]
            followers += pg.get("follower_count") or 0
            if pg["health_status"] == "Healthy": healthy += 1
            if pg["restriction_status"] == "Restricted": restricted += 1
            pages.append(pg)
        details["pages"] = pages
        details["summary"] = {"page_count": len(pages), "total_followers": followers,
                              "healthy_pages": healthy, "restricted_pages": restricted,
                              "needs_check_pages": len(pages) - healthy}
        return details

    # ---------- Pages ----------
    def add_page(self, facebook_page_id, page_name, page_url=None, category=None,
                 follower_count=None, notes=None, manual_status="Unknown", data_source="manual"):
        if not facebook_page_id: raise ValueError("Facebook Page ID is required")
        if not page_name or not page_name.strip(): raise ValueError("Page name is required")
        if self.conn.execute("SELECT 1 FROM pages WHERE facebook_page_id=?", (facebook_page_id,)).fetchone():
            raise DuplicateError(f"Page with ID {facebook_page_id} already exists")
        t = now_iso()
        cur = self.conn.execute(
            """INSERT INTO pages(facebook_page_id,page_name,page_url,category,follower_count,notes,
               manual_status,data_source,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (facebook_page_id, page_name.strip(), page_url, category, follower_count, notes, manual_status, data_source, t, t))
        self.conn.commit(); return cur.lastrowid

    def update_page(self, pgid, **fields):
        allowed = {"page_name","page_url","category","follower_count","notes","manual_status","last_checked_at"}
        sets = {k:v for k,v in fields.items() if k in allowed}
        if not sets: return
        sets["updated_at"] = now_iso()
        self.conn.execute(f"UPDATE pages SET {','.join(k+'=?' for k in sets)} WHERE id=?",
                          (*sets.values(), pgid)); self.conn.commit()

    def delete_page(self, pgid):
        self.conn.execute("DELETE FROM pages WHERE id=?", (pgid,)); self.conn.commit()

    def link_profile_page(self, profile_id, page_id, access_role=None, access_status="Unknown"):
        self.conn.execute(
            """INSERT INTO profile_page_access(profile_id,page_id,access_role,access_status,last_seen_at)
               VALUES(?,?,?,?,?) ON CONFLICT(profile_id,page_id) DO UPDATE SET access_role=excluded.access_role,
               access_status=excluded.access_status,last_seen_at=excluded.last_seen_at""",
            (profile_id, page_id, access_role, access_status, now_iso())); self.conn.commit()

    def list_pages(self, search=None, profile_id=None, manual_status=None):
        q = """SELECT p.*, GROUP_CONCAT(pr.display_name) AS profiles
               FROM pages p LEFT JOIN profile_page_access a ON a.page_id=p.id
               LEFT JOIN profiles pr ON pr.id=a.profile_id WHERE 1=1"""; args=[]
        if search:
            q += " AND (p.page_name LIKE ? OR p.facebook_page_id LIKE ? OR p.page_url LIKE ?)"; args += [f"%{search}%"]*3
        if profile_id: q += " AND a.profile_id=?"; args.append(profile_id)
        if manual_status: q += " AND p.manual_status=?"; args.append(manual_status)
        q += " GROUP BY p.id ORDER BY p.page_name"
        return [dict(r) for r in self.conn.execute(q, args)]

    def mark_missing_pages(self, profile_id, seen_page_ids):
        """Pages no longer in an API response are flagged, never auto-deleted (Section 5)."""
        rows = self.conn.execute(
            """SELECT p.id,p.facebook_page_id FROM pages p JOIN profile_page_access a ON a.page_id=p.id
               WHERE a.profile_id=?""", (profile_id,)).fetchall()
        missing = [r["id"] for r in rows if r["facebook_page_id"] not in seen_page_ids]
        for pgid in missing: self.update_page(pgid, manual_status="Missing - Verify")
        return missing

    def page_profile_ids(self, page_id):
        return [r["profile_id"] for r in self.conn.execute(
            "SELECT profile_id FROM profile_page_access WHERE page_id=?", (page_id,))]

    # ---------- Health & Monetization ----------
    def record_health(self, page_id, technical="Unknown", policy="Unknown", restriction="Unknown",
                      error=None, source="manual"):
        self.conn.execute(
            "INSERT INTO page_health_history(page_id,checked_at,technical_connection_status,policy_status,restriction_status,error_details,data_source) VALUES(?,?,?,?,?,?,?)",
            (page_id, now_iso(), technical, policy, restriction, error, source))
        self.update_page(page_id, last_checked_at=now_iso()); self.conn.commit()

    def latest_health(self, page_id):
        r = self.conn.execute("SELECT * FROM page_health_history WHERE page_id=? ORDER BY id DESC LIMIT 1", (page_id,)).fetchone()
        return dict(r) if r else {"technical_connection_status":"Unknown","policy_status":"Unknown",
                                  "restriction_status":"Manual Check Required","checked_at":None,"data_source":"none"}

    def health_history(self, page_id):
        return [dict(r) for r in self.conn.execute("SELECT * FROM page_health_history WHERE page_id=? ORDER BY id DESC", (page_id,))]

    def record_monetization(self, page_id, api_status="Unknown", eligibility="Unknown", products=None,
                            restriction=None, source="manual", manual_status="Not Verified", notes=None):
        self.conn.execute(
            "INSERT INTO monetization_history(page_id,checked_at,api_status,eligibility_status,available_products,restriction_details,data_source,manual_status,notes) VALUES(?,?,?,?,?,?,?,?,?)",
            (page_id, now_iso(), api_status, eligibility, products, restriction, source, manual_status, notes)); self.conn.commit()

    def latest_monetization(self, page_id):
        r = self.conn.execute("SELECT * FROM monetization_history WHERE page_id=? ORDER BY id DESC LIMIT 1", (page_id,)).fetchone()
        return dict(r) if r else {"api_status":"Unknown","eligibility_status":"Unknown",
                                   "manual_status":"Not Verified","checked_at":None,"data_source":"none"}

    # ---------- Sync logs ----------
    def add_sync_log(self, profile_id, result, pages_processed=0, error=None, started_at=None):
        self.conn.execute("INSERT INTO sync_logs(profile_id,started_at,finished_at,result,pages_processed,error_message) VALUES(?,?,?,?,?,?)",
                          (profile_id, started_at or now_iso(), now_iso(), result, pages_processed, error)); self.conn.commit()
    def list_sync_logs(self, profile_id=None):
        q="SELECT * FROM sync_logs"; args=[]
        if profile_id: q+=" WHERE profile_id=?"; args.append(profile_id)
        return [dict(r) for r in self.conn.execute(q+" ORDER BY id DESC", args)]

    # ---------- App users / login (Section 15) ----------
    def create_user(self, username, password, role="Licensed User"):
        if role not in ("Super Admin","Admin","Licensed User"): raise ValueError("Invalid role")
        try:
            cur = self.conn.execute("INSERT INTO app_users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                                    (username, hash_password(password), role, now_iso())); self.conn.commit(); return cur.lastrowid
        except sqlite3.IntegrityError: raise DuplicateError(f"User {username} already exists")
    def verify_user(self, username, password):
        r = self.conn.execute("SELECT * FROM app_users WHERE username=? AND is_active=1", (username,)).fetchone()
        return dict(r) if r and verify_password(password, r["password_hash"]) else None
    def has_super_admin(self):
        return self.conn.execute("SELECT 1 FROM app_users WHERE role='Super Admin'").fetchone() is not None

    # ---------- Settings / audit / dashboard ----------
    def set_setting(self, k, v): self.conn.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,v)); self.conn.commit()
    def get_setting(self, k, default=None):
        r = self.conn.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone(); return r["value"] if r else default
    def audit(self, actor, action, details=None):
        self.conn.execute("INSERT INTO audit_logs(actor,action,details,created_at) VALUES(?,?,?,?)",(actor,action,details,now_iso())); self.conn.commit()

    def dashboard_stats(self):
        c = self.conn
        total_profiles = c.execute("SELECT COUNT(*) x FROM profiles").fetchone()["x"]
        connected = c.execute("SELECT COUNT(*) x FROM profiles WHERE connection_status='Connected'").fetchone()["x"]
        total_pages = c.execute("SELECT COUNT(*) x FROM pages").fetchone()["x"]
        def latest_status_count(table, col, val):
            return c.execute(f"""SELECT COUNT(*) x FROM pages p WHERE
                (SELECT {col} FROM {table} h WHERE h.page_id=p.id ORDER BY h.id DESC LIMIT 1)=?""", (val,)).fetchone()["x"]
        healthy = latest_status_count("page_health_history","technical_connection_status","Healthy")
        warnings = latest_status_count("page_health_history","technical_connection_status","Warning")
        restricted = latest_status_count("page_health_history","restriction_status","Restricted")
        monet_known = c.execute("""SELECT COUNT(DISTINCT page_id) x FROM monetization_history WHERE api_status!='Unknown'""").fetchone()["x"]
        sync_fail = c.execute("SELECT COUNT(*) x FROM sync_logs WHERE result='Failed'").fetchone()["x"]
        return {"total_profiles": total_profiles, "connected_profiles": connected, "total_pages": total_pages,
                "healthy_pages": healthy, "warning_pages": warnings, "restricted_pages": restricted,
                "manual_verification_pages": max(total_pages - healthy - warnings - restricted, 0),
                "monetization_known": monet_known, "monetization_unknown": total_pages - monet_known,
                "sync_failures": sync_fail}
