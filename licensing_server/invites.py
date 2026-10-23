"""Server-side store for profile invites (connect-by-link).

An invite is created by the admin's desktop app (which generates the unguessable
code) and registered here. When the profile owner completes Facebook Login via
/connect, the accepted payload (profile + Pages + the long-lived user token) is
stored against the code until the desktop app fetches it once and reports
'consumed' — at which point the token copy held here is wiped. Same SQLite file
as the license store in dev (FPM_LICENSE_DB); schema is plain SQL so it ports to
PostgreSQL with the rest of the deployment pack.
"""
import json, sqlite3
from datetime import datetime, timezone

def _now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile_invites(
 code TEXT PRIMARY KEY, display_name TEXT, profile_link TEXT, note TEXT,
 status TEXT DEFAULT 'pending', payload_json TEXT,
 created_at TEXT, accepted_at TEXT, consumed_at TEXT);
"""

class InviteStore:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def register(self, code, display_name=None, profile_link=None, note=None):
        """Idempotent: re-registering an existing code never resets its status."""
        self.conn.execute(
            """INSERT INTO profile_invites(code,display_name,profile_link,note,status,created_at)
               VALUES(?,?,?,?, 'pending', ?)
               ON CONFLICT(code) DO UPDATE SET
                 display_name=COALESCE(excluded.display_name, profile_invites.display_name),
                 profile_link=COALESCE(excluded.profile_link, profile_invites.profile_link),
                 note=COALESCE(excluded.note, profile_invites.note)""",
            (code, display_name, profile_link, note, _now()))
        self.conn.commit()
        return self.get(code)

    def get(self, code):
        r = self.conn.execute("SELECT * FROM profile_invites WHERE code=?", (code,)).fetchone()
        return dict(r) if r else None

    def mark_accepted(self, code, payload):
        cur = self.conn.execute(
            "UPDATE profile_invites SET status='accepted', payload_json=?, accepted_at=? WHERE code=?",
            (json.dumps(payload), _now(), code))
        self.conn.commit()
        return cur.rowcount > 0

    def mark_consumed(self, code):
        """Desktop has imported the payload: wipe the stored token copy for safety."""
        cur = self.conn.execute(
            "UPDATE profile_invites SET status='consumed', payload_json=NULL, consumed_at=? WHERE code=?",
            (_now(), code))
        self.conn.commit()
        return cur.rowcount > 0

    def public_view(self, row):
        """What the status API returns. The payload (incl. token) is exposed ONLY
        while status == 'accepted' and ONLY to whoever holds the invite code."""
        out = {"code": row["code"], "status": row["status"],
               "display_name": row.get("display_name"), "created_at": row.get("created_at"),
               "accepted_at": row.get("accepted_at")}
        if row["status"] == "accepted" and row.get("payload_json"):
            payload = json.loads(row["payload_json"])
            out.update(payload)  # {profile, pages, access_token}
        return out
