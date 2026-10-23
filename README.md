# Facebook Pages Manager

**Owner:** Muhammad Aamir (Super Admin) · **Email:** onlineworking07861@gmail.com · **Phone:** 03021052317
**Platform:** Windows 10/11 desktop (Python + PySide6) · **Version:** 1.0.0 — All 6 phases (code complete)

Professional desktop software to manage multiple authorized Facebook profiles and their Pages,
view Page health / monetization information where the official Meta API exposes it, and export
reports — with an online license-key system for authorized customer distribution.

## Status — all 6 phases, code complete (52 automated tests passing)
- ✅ **Phase 1 — Local MVP:** PySide6 UI (Dashboard, Profiles, Pages, Health, Monetization, Sync Logs,
  Reports, License, Settings, About), SQLite DB with duplicate protection, CRUD/search/filter,
  CSV/Excel/PDF exports, CSV import with preview, backup/restore, hashed local users + roles.
- ✅ **Phase 2 — Meta integration:** documented Graph API endpoints only, official OAuth (browser
  login, loopback + state check), server-side token exchange (App Secret never in the desktop app),
  encrypted token store, sync engine with dedupe + missing-Page flagging. Setup: `docs/META_SETUP.md`.
- ✅ **Phase 3 — Health & monetization:** real technical health checks via the API; policy/monetization
  are NEVER invented — the API does not expose them, so they use a dated manual-verification workflow
  with history, kept separate from API data. Follower count never implies eligibility.
- ✅ **Phase 4 — Licensing backend hardening:** Argon2id server accounts, one-time Super Admin
  bootstrap, sessions, server-side RBAC (destructive actions = Super Admin only), login lockout
  (5 failures / 15 min), API rate limiting, audit logs, Docker deployment pack.
- ✅ **Phase 5 — Desktop licensing:** functional activation screen, Ed25519-signed licenses verified
  on the desktop with the PUBLIC key only, encrypted license cache, offline grace period (7 days,
  configurable), expiry warnings, license gate on Meta features (local data is never deleted).
- ✅ **Phase 6 — Release:** PyInstaller spec + build script + Inno Setup installer script, user
  guide, deployment guide, troubleshooting. The packaging was built and the packaged app was
  run successfully on the build machine (Linux binary) — the **Windows** .exe/Setup must be built
  with the same script on a Windows PC.

## Known external requirements (not code — cannot be done inside this repo)
1. **Your Meta developer app** (App ID; secret set on the server only) + Meta App Review for
   managing other people's Pages. See `docs/META_SETUP.md`.
2. **A server/VPS** to host the licensing backend. `docker-compose.yml` + `docs/DEPLOYMENT.md`.
   PostgreSQL schema ships in `docs/postgres_schema.sql`; the tested store logic runs on SQLite —
   the PostgreSQL connection layer must be verified against your live Postgres before production
   and is not claimed as tested here.
3. **Windows build machine** for the final `.exe` + installer and clean-Windows testing.

## Install & run (development)
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py --setup-admin aamir      :: first run only — creates Super Admin, you choose the password
python app.py
```

## Tests
```bat
pip install pytest openpyxl reportlab fastapi httpx PySide6
python -m pytest tests\ -q
```
Final test result on the build machine (Linux VM): **52 passed, 0 failed** — CRUD, duplicates,
search, missing-page flagging, exports/import, backup/restore, dashboard stats, user roles,
mocked Meta API (paging, error mapping, rate-limit retry), OAuth state/callback, encrypted token
storage, sync dedupe/expiry, technical health checks, manual health/monetization verification,
Argon2 server auth with lockout + RBAC, the full licensing lifecycle, Ed25519 desktop activation
with tamper rejection, FastAPI endpoints, and the PySide6 GUI smoke test. The PyInstaller-packaged
app was also built and launched successfully on the build machine.

## Licensing server (development)
```bat
pip install -r licensing_server\requirements.txt
set FPM_SIGNING_SECRET=<long random secret — SERVER ONLY, never put in the desktop app>
set FPM_ADMIN_TOKEN=<bootstrap admin token — SERVER ONLY>
uvicorn licensing_server.main:app --host 0.0.0.0 --port 8000
```
Production: put it behind HTTPS, move to PostgreSQL, rotate the bootstrap token after Super Admin setup.

## Windows executable
```bat
python scripts\build_windows.py
```
Produces `dist\FacebookPagesManager\FacebookPagesManager.exe`. Test on a clean Windows 10/11 machine
before distributing. An installer (Inno Setup) is a Phase 6 item.

## Meta developer setup (Phase 2 preview)
1. Create an app at https://developers.facebook.com → type Business.
2. Add Facebook Login, set a valid OAuth redirect URI (desktop loopback).
3. Request only needed permissions (e.g. `pages_show_list`, `pages_read_engagement`); several need
   App Review / Advanced Access — the app shows `Permission Missing` until granted.
4. Put the App ID in Settings / `FPM_META_APP_ID`. **Never** put the App Secret in the desktop app.

## Security rules enforced in code
- Facebook passwords are never asked for, stored, or logged. OAuth only (Phase 2).
- Access tokens, passwords, signing secrets are never written to logs, exports, or backups of settings.
- Licensing decisions are server-authoritative; a local file alone never validates a license.
- Ordinary users cannot promote themselves to Admin/Super Admin (server-side RBAC in Phase 4).

## Troubleshooting
- *App won't start, Qt platform error (Linux dev only):* install system GL libs or run on Windows.
- *Export says file exists:* by design — pick a new filename; the app never silently overwrites.
- *License activation unavailable:* expected in Phase 1 until the Phase 5 server connection is enabled.
- *Page shows Unknown health:* no verified API/manual data exists yet — use Record Manual Check or Phase 2/3.
