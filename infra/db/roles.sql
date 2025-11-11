-- Database role hardening for Smart Data Pipeline
-- Run once per environment (dev/prod). Replace passwords with secrets from your vault.

-- Primary schema owner used only for migrations / schema changes.
CREATE ROLE sdp_migrations LOGIN PASSWORD '<rotate-me>' NOSUPERUSER NOCREATEDB;

-- Runtime application user (least privilege). Application DATABASE_URL should use this role.
CREATE ROLE sdp_app LOGIN PASSWORD '<rotate-me-too>' NOSUPERUSER NOCREATEDB;

-- Optional read-only analyst role (no inserts/updates).
CREATE ROLE sdp_readonly LOGIN PASSWORD '<optional-ro-pass>' NOSUPERUSER NOCREATEDB;

-- Ensure roles can reach the database & schema.
GRANT CONNECT ON DATABASE smartdata TO sdp_migrations, sdp_app, sdp_readonly;
GRANT USAGE ON SCHEMA public TO sdp_migrations, sdp_app, sdp_readonly;

-- Migration role keeps full DDL/DML rights.
GRANT ALL PRIVILEGES ON SCHEMA public TO sdp_migrations;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO sdp_migrations;

-- Runtime role receives data-only rights (no DDL).
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sdp_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sdp_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sdp_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO sdp_app;

-- Optional: read-only grants.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sdp_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO sdp_readonly;

-- Enforce TLS and lock down the runtime role.
ALTER ROLE sdp_app SET sslmode = 'require';
ALTER ROLE sdp_app SET idle_in_transaction_session_timeout = '15s';

-- Reminder: rotate credentials each release and store them in your secret manager.
