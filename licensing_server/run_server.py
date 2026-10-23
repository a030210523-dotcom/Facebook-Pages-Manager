"""Standalone entry point for the licensing server executable (FPMLicenseServer.exe).

Built with LicenseServer.spec (PyInstaller, one file, console) so the server runs
on any Windows PC with NOTHING installed — no Python required.
Configuration is via environment variables, exactly like the uvicorn route:
  FPM_ED25519_PRIVATE_KEY  (required for real licenses — set by the launcher .bat)
  FPM_ADMIN_TOKEN          admin/bootstrap token
  FPM_LICENSE_DB           SQLite path (default: licenses.db next to the exe)
  FPM_PUBLIC_BASE_URL      public URL when deployed (invite links)
  META_APP_ID / META_APP_SECRET / META_API_VERSION
  FPM_HOST / FPM_PORT      bind address (default 127.0.0.1:8000)
"""
import os, sys


def _default_db_path():
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
    return os.path.join(base, "licenses.db")


def main():
    os.environ.setdefault("FPM_LICENSE_DB", _default_db_path())
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from licensing_server.main import app
    import uvicorn
    host = os.environ.get("FPM_HOST", "127.0.0.1")
    port = int(os.environ.get("FPM_PORT", "8000"))
    print(f"FPM Licensing Server starting on http://{host}:{port} — keep this window open.")
    if not os.environ.get("FPM_ED25519_PRIVATE_KEY"):
        print("WARNING: FPM_ED25519_PRIVATE_KEY is not set — license activation will fail. "
              "Start the server via START_LICENSE_SERVER.bat from the Owner Pack.")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
