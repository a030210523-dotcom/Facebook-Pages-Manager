# User Guide — Facebook Pages Manager
Owner: Muhammad Aamir · onlineworking07861@gmail.com · 03021052317

## First run
1. Install and open the app. Create the owner account when asked:
   (owner setup) `python app.py --setup-admin yourname` — packaged builds show the setup on first launch.
2. Go to **License Management**, enter your license key, press **Activate** (internet required once).

## Daily use
- **Facebook Profiles** → Connect Facebook (OAuth) — login happens in your browser; the app
  never asks for your Facebook password. Then **Sync Pages** to import your Pages.
- **All Pages** — search, edit manual fields, open/copy Page links, add Pages manually.
- **Page Health** — *Run Technical Check* verifies the connection through Meta's API.
  Policy status needs your manual verification from Meta Business Suite (button provided).
- **Monetization** — Meta's API does not expose eligibility to apps; verify in the official
  dashboard (button provided) and record the result — it is stored with date and history.
- **Reports and Exports** — Excel/CSV/PDF reports, CSV import, database backup/restore.
- **License Management** — shows status, expiry, and offline-grace state. If you change
  computer, contact the owner to free a device slot.

## If something looks wrong
- "Permission Missing" → the Meta app lacks an approved permission (see docs/META_SETUP.md).
- "Token Expired" → reconnect the profile from Facebook Profiles.
- "Online Validation Required" → connect to the internet once so the license can re-validate.
- License expired/suspended → contact the owner (details above). Your data is never deleted
  because a license expires; export it any time from Reports.
