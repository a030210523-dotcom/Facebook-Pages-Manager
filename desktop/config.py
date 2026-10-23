"""Centralized branding & settings — change owner info HERE only (Section 2/26)."""
import os

APP_NAME = "Facebook Pages Manager"
APP_VERSION = "0.1.0-phase1"
OWNER_NAME = "Muhammad Aamir"
OWNER_EMAIL = "onlineworking07861@gmail.com"
OWNER_PHONE = "03021052317"
OWNER_ROLE = "Super Admin"

# Meta (Phase 2) — App Secret must NEVER be stored in the desktop app.
META_API_VERSION = os.environ.get("FPM_META_API_VERSION", "v21.0")
META_APP_ID = os.environ.get("FPM_META_APP_ID", "")

# Licensing server (Phase 4/5) — public URL only, no secrets here.
LICENSING_SERVER_URL = os.environ.get("FPM_LICENSE_SERVER_URL", "https://localhost:8000")
OFFLINE_GRACE_DAYS = int(os.environ.get("FPM_OFFLINE_GRACE_DAYS", "7"))

def app_data_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".facebook_pages_manager")
    path = os.path.join(base, "FacebookPagesManager")
    os.makedirs(path, exist_ok=True)
    return path

def default_db_path() -> str:
    return os.path.join(app_data_dir(), "fpm_local.db")
