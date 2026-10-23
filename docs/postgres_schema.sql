-- Facebook Pages Manager — Licensing backend, PostgreSQL production schema (Phase 4).
-- Mirrors the SQLite dev schema 1:1 so the same core logic runs on both.
-- Apply with: psql "$DATABASE_URL" -f docs/postgres_schema.sql
-- Migrations in production: manage changes with Alembic against this baseline.

CREATE TABLE IF NOT EXISTS licenses(
  id SERIAL PRIMARY KEY, key_hash TEXT UNIQUE NOT NULL, key_last4 TEXT,
  customer_name TEXT NOT NULL, customer_email TEXT, customer_phone TEXT,
  license_type TEXT NOT NULL, issued_at TIMESTAMPTZ, expiry_date TIMESTAMPTZ,
  max_devices INTEGER DEFAULT 1, status TEXT DEFAULT 'Pending Activation', notes TEXT);
CREATE TABLE IF NOT EXISTS activations(
  id SERIAL PRIMARY KEY, license_id INTEGER NOT NULL REFERENCES licenses(id),
  installation_id TEXT NOT NULL, device_label TEXT, activated_at TIMESTAMPTZ,
  last_validated_at TIMESTAMPTZ, app_version TEXT, status TEXT DEFAULT 'Active',
  UNIQUE(license_id, installation_id));
CREATE TABLE IF NOT EXISTS audit_logs(
  id SERIAL PRIMARY KEY, actor TEXT, action TEXT, details TEXT, created_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS server_users(
  id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'Licensed User', is_active INTEGER DEFAULT 1,
  failed_attempts INTEGER DEFAULT 0, locked_until TIMESTAMPTZ, created_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS sessions(
  token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES server_users(id),
  expires_at TIMESTAMPTZ, created_at TIMESTAMPTZ);
CREATE TABLE IF NOT EXISTS user_audit(
  id SERIAL PRIMARY KEY, actor TEXT, action TEXT, details TEXT, created_at TIMESTAMPTZ);
CREATE INDEX IF NOT EXISTS idx_licenses_status ON licenses(status);
CREATE INDEX IF NOT EXISTS idx_activations_license ON activations(license_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
