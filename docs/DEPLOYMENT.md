# Licensing Server Deployment Guide (Phase 4)

## Option A — Docker (recommended)
1. On a VPS (Ubuntu), install Docker, copy this project, `cp .env.example .env`.
2. Generate the signing keypair:
   `python -c "from licensing_server.signing import generate_keypair; print(generate_keypair())"`
   Put the **private** key in `.env` (`FPM_ED25519_PRIVATE_KEY`). The public key is served
   automatically at `GET /api/license/public-key`; optionally pin it in customer builds via
   env `FPM_LICENSE_PUBLIC_KEY` on the desktop.
3. Set a long random `FPM_ADMIN_TOKEN` and `POSTGRES_PASSWORD`, fill Meta app values.
4. `docker compose up -d`, then put Caddy/Nginx with TLS in front of port 8000.
5. Bootstrap the owner account (one time):
   `POST /api/auth/bootstrap-super-admin` with header `x-admin-token: <FPM_ADMIN_TOKEN>`
   and JSON `{username, password}` → creates Muhammad Aamir's Super Admin. After this,
   rotate/remove routine use of the bootstrap token; manage users via Super Admin sessions.
6. Daily backups: `pg_dump` the `fpm_licenses` database + keep the `.env` in a password manager.

## Option B — Plain Python (dev / small installs)
`pip install -r licensing_server/requirements.txt`, set the same env vars,
`uvicorn licensing_server.main:app --host 0.0.0.0 --port 8000`. Dev mode uses SQLite
(`FPM_LICENSE_DB`); the business logic and tests are identical.

## PostgreSQL status (honest note)
The production PostgreSQL **schema ships in `docs/postgres_schema.sql`** and the compose
stack provisions Postgres with it. The application store currently executes the same
tested logic on SQLite; moving the store's connection layer to PostgreSQL (psycopg +
`DATABASE_URL`) is the one remaining server task and must be verified against a live
Postgres before production — it is **not** claimed as done/tested here.

## Security checklist
- HTTPS only in production; rate limits are in the app AND should exist at the proxy.
- Secrets only in server env; the desktop contains no secret and no private key.
- Argon2id password hashing; 5 failed logins lock an account for 15 minutes (audited).
- Audit logs cover license create/suspend/revoke/renew, device deactivation, user/role changes, logins.
