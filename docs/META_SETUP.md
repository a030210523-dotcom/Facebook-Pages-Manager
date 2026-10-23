# Meta Developer Setup — Facebook Pages Manager (Phase 2)

## 1. Create the Meta app
1. Go to https://developers.facebook.com/apps → Create App → type **Business**.
2. Add the **Facebook Login** product.
3. In Facebook Login → Settings, add this Valid OAuth Redirect URI pattern (the app uses a
   loopback port on the user's own PC): `http://127.0.0.1/` — also add the app under
   Settings → Advanced → allow loopback if prompted for native/desktop flows.

## 2. Permissions the app requests (least privilege)
- `public_profile` — default, identifies the connected user (`/me`).
- `pages_show_list` — lists Pages the user is authorized for (`/me/accounts`).
- `pages_read_engagement` — Page metadata used by health checks.

**App Review reality:** In Development mode these work for the app owner/admins/testers and
their own Pages. To manage *customers'* Pages, submit for **App Review / Advanced Access**
for `pages_show_list` and `pages_read_engagement`, with a screencast showing the login +
Page discovery flow. Until approved, other users will see **Permission Missing** — the app
reports that honestly instead of failing silently.

## 3. Where secrets go (important)
- **App ID** — safe in the desktop app (Settings / env `FPM_META_APP_ID`).
- **App Secret** — **SERVER ONLY**. Set on the licensing server:
  `META_APP_ID`, `META_APP_SECRET`, `META_API_VERSION` (default `v21.0`).
  The desktop sends only the one-time OAuth `code` to `POST /api/meta/token-exchange`;
  the server exchanges it (including the long-lived `fb_exchange_token` grant) and returns
  the token. The secret never ships inside the .exe.

## 4. Run the full flow locally
Server:
```bat
set FPM_SIGNING_SECRET=<random>
set FPM_ADMIN_TOKEN=<random>
set META_APP_ID=<your app id>
set META_APP_SECRET=<your app secret>
uvicorn licensing_server.main:app --port 8000
```
Desktop: set the licensing server URL in config (env `FPM_LICENSE_SERVER_URL`, default
`https://localhost:8000` — use your real HTTPS server URL in production), then
Profiles → **Connect Facebook (OAuth)** → login in browser → **Sync Pages (Selected)**.

## 5. Tokens
- Stored encrypted (Fernet) in the app-data folder; shown only masked (`EAA…xyz`).
- Never written to logs, exports, or backups. Disconnect = delete the profile or remove
  `tokens.enc` entry (Profiles → delete), and revoke in Facebook Settings → Apps.

## 6. API version
Centralized in `desktop/config.py` (`META_API_VERSION`). When Meta deprecates a version,
change it in one place and re-run the tests.

## 7. Invite a profile by link (connect link flow)
For profiles owned by OTHER people (clients/team), do not ask them to visit your
PC. In the app: Facebook Profiles -> "Invite Profile (Link)" -> enter their name
and Facebook profile link -> the app creates a connect link
`{LICENSING_SERVER_URL}/connect?invite=CODE`. Send it to the owner (Messenger /
WhatsApp / email). The owner opens it, taps "Continue with Facebook", logs in on
facebook.com and accepts the permissions; the server stores the connection
against the code. Back in the app, select the invite -> "Check Invite Status":
the profile and ALL its Pages (with roles, categories, follower counts) are
imported automatically and the token is stored encrypted on your PC; the
server then wipes its token copy.

Requirements for this to work for other people:
- The licensing server must be reachable on a PUBLIC https URL (VPS) and
  `FPM_PUBLIC_BASE_URL` set to it, because the owner opens the link from their
  own phone/PC.
- `META_APP_ID` / `META_APP_SECRET` set in the SERVER environment (section 1),
  and the Facebook Login product's Valid OAuth Redirect URIs must include
  `{FPM_PUBLIC_BASE_URL}/auth/facebook/callback`.
- Managing other people's Pages needs Meta App Review + Advanced Access for
  `pages_show_list` / `pages_read_engagement`; until granted, owners will see a
  permission error and the invite simply stays Pending.
Note: Facebook does not offer any API to push a permission notification into
someone's Facebook account or to read a profile from its link — the connect
link above is the official equivalent: the owner always approves on Facebook's
own screens.
