# Security Hardening Guide

> Applies to the QR-4 security milestone. Follow these controls for every production deployment.

## 1. Network & Transport Controls

- **HTTPS-only:** The public frontend/API must terminate behind your CDN or load balancer with HTTP→HTTPS redirects enabled. In FastAPI set `FORCE_HTTPS=true` to mirror the redirect and set `TRUSTED_HOSTS` to your domains.
- **TLS 1.2+ end-to-end:** CDN/edge must refuse TLS < 1.2. Upstream connections (edge → FastAPI → Postgres) are required to use TLS (see `DB_REQUIRE_SSL`).
- **Security headers:** The backend now injects `Strict-Transport-Security` (preload + subdomains), `Content-Security-Policy`, `Referrer-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, and `Permissions-Policy`. Override the CSP via `CONTENT_SECURITY_POLICY` if you add additional origins.
- **Verification:** Capture evidence in every security PR by attaching:
  ```bash
  curl -Ik https://<prod-domain>/health
  openssl s_client -connect <prod-domain>:443 -tls1_2 </dev/null
  ```
  The first proves HTTPS/HSTS headers, the second proves TLS ≥ 1.2 support.

## 2. Application Settings

Environment variables (set via your secret manager):

| Var | Purpose |
| --- | --- |
| `FORCE_HTTPS` | Enables HTTPS redirect + HSTS |
| `TRUSTED_HOSTS` | Whitelisted hostnames |
| `CONTENT_SECURITY_POLICY` | CSP string |
| `DB_REQUIRE_SSL` (default `true`) | Forces `sslmode=require` |
| `DB_APP_ROLE` | Expected Postgres role; app fails fast if the URL uses any other role |
| `APP_ENCRYPTION_KEY` | Fernet key used for app-layer encryption |

Sensitive payloads (`raw_events.payload`) are now encrypted at the ORM layer before touching the database. Supply a 32-byte Fernet key (or any string—non-base64 strings are SHA-256 derived automatically). Rotate by:
1. Deploy with `APP_ENCRYPTION_KEY_NEXT`
2. Backfill rows (script forthcoming)
3. Switch traffic and retire the old key

## 3. Database Security

- Use managed PostgreSQL with storage encryption turned on. For local testing use SQLite on FileVault/APFS or SQLCipher.
- `infra/db/roles.sql` provisions:
  - `sdp_migrations`: full DDL for Alembic migrations only
  - `sdp_app`: runtime service account (only CRUD)
  - `sdp_readonly`: optional analyst role
- The app verifies that `DATABASE_URL` uses `sdp_app` (or the role configured in `DB_APP_ROLE`). Provide a read-only URL to analytics jobs instead.

## 4. Secrets & CI/CD

- **Secret storage:** Keep `DATABASE_URL`, JWT secrets, encryption keys, API keys, etc., inside your production secret store (GitHub Actions environments, AWS/GCP/Azure Secret Manager, 1Password Secrets Automation, etc.). `.env` files are for local development only.
- **OIDC deployments:** Use GitHub’s OpenID Connect integration with your cloud provider so CI jobs can assume deploy roles without long-lived keys. Update the README deploy section whenever credentials rotate.
- **Rotation policy:** Rotate DB, JWT, and encryption keys at least every release (or immediately after suspected exposure). Document rotation dates inside your change log / runbook.

## 5. CI “Security” Job

A new workflow job runs dependency audits (`pip-audit`, `npm audit`) and static analysis (`bandit`, `eslint --max-warnings=0`). Treat this job as required before merging.

## 6. Quick Verification Tests

- `backend/tests/test_security_headers.py::test_security_headers_in_prod` asserts the FastAPI stack emits HSTS/CSP headers when prod settings are enabled.
- `backend/tests/test_security_headers.py::test_required_db_role_enforced` ensures we only run with the restricted Postgres role.

Run `pytest backend/tests/test_security_headers.py -q` locally after editing security sensitive code.

## 7. Incident & Disclosure

- Use GitHub Security Advisories for coordinated disclosure.
- Report suspected vulnerabilities to the maintainers via the private contact information in the README (add your SOC/alias as needed).

Keep this document updated whenever you change infra, TLS, or secret handling.
