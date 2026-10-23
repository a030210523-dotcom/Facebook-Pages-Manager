# Licensing Server
FastAPI service — see `main.py` for endpoints (Section 18 of the master prompt) and `core.py` for the
tested licensing logic. Dev uses SQLite (`FPM_LICENSE_DB`); production deployment: PostgreSQL +
SQLAlchemy/Alembic, Argon2id password hashing, HTTPS via reverse proxy, rate limiting on
`/api/license/*` and admin auth, daily DB backups, `FPM_SIGNING_SECRET` and `FPM_ADMIN_TOKEN`
set only in the server environment.
