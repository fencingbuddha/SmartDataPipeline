# Known Issues & Technical Limitations (Project-Level)

This document summarizes architectural constraints, technical limitations, and non-critical issues that remain in the SmartDataPipeline project. These items do **not** block functionality for the capstone but represent areas for future improvement if the system were deployed in production.

---

## 1. SQLite Limitations in Portable Build
The portable demo uses SQLite instead of PostgreSQL, which introduces the following constraints:

- No concurrent write safety for high‑volume ingestion workloads.
- Limited query performance for large datasets or frequent analytical queries.
- No native support for advanced indexing strategies (GIN/GIST) or JSONB.
- APScheduler database-backed distributed job stores are not available.

**Impact:** Suitable for demos and single-user environments only. Production must use PostgreSQL.

---

## 2. No Role-Based Access Control (RBAC)
Authentication is implemented with JWT access/refresh tokens, but:

- All authenticated users have the same permission level.
- No distinction exists between admin, analyst, or read‑only users.
- No organization-level or tenant-level authorization.

**Impact:** Acceptable for single-user demo purposes but insufficient for enterprise environments.

---

## 3. Missing Pagination on Large Datasets
API endpoints such as:

- `/api/metrics/daily`
- `/api/ingest` history reads
- `/api/sources`

return full datasets without pagination or streaming.

**Impact:** Works for capstone-scale datasets but could lead to slow responses or excessive memory usage in production.

---

## 4. Forecasting Model Limitations
The SARIMAX forecasting engine includes safeguards but has known constraints:

- Forecast accuracy decreases when dataset length is < 30 days.
- Fallback constant model activates when SARIMAX cannot converge.
- No hyperparameter optimization or automated model selection (e.g., AutoARIMA or Prophet).

**Impact:** Reliable enough for demo usage but not production-grade forecasting.

---

## 5. Isolation Forest Anomaly Detector – Single Model Only
The anomaly overlay endpoint exists for UAT contract compatibility, but:

- The Isolation Forest model is not persisted across runs.
- No per-source or per‑metric model specialization.
- No drift detection or retraining triggers beyond scheduled jobs.

**Impact:** Functional, but anomaly quality may vary depending on input dataset composition.

---

## 6. Scheduler Limitations (APScheduler)
APScheduler works well locally, but:

- It is not configured for distributed environments.
- Job persistence is not enabled.
- No “exclusive lock” mechanism ensures only one scheduler runs in multi-instance deployments.

**Impact:** Fine for local single-instance execution; production would require a centralized job queue (Redis/RQ, Celery, or PostgreSQL job store).

---

## 7. Dev/Portable CORS Settings Are Broad
CORS settings allow all local development origins:

- `http://localhost:5173`
- `http://127.0.0.1:*`

**Impact:** Safe for development and demo environments, but real deployments must narrow allowed origins.

---

## 8. Swagger UI Limited When Unauthenticated
By design, most routes require authentication. However:

- Swagger UI does not automatically attach JWT tokens.
- Some endpoints appear “missing” to users until they sign in.

**Impact:** Expected behavior but can confuse new users evaluating the system.

---

## 9. CI Pipeline Omits Browser-Based Tests
CI includes:

- Backend pytest suite
- pip-audit and Bandit
- ESLint and npm audit

But CI **does not** run Cypress UI tests.

**Impact:** Snapshot/UI regressions must be caught manually in local development.

---

## 10. No Data Retention Policy or Log Rotation
The system includes structured logging but:

- Logs are not rotated.
- No archival/deletion mechanism exists.
- No purging policy for raw events or metric archives.

**Impact:** Demo-ready but not suitable for long-running production deployments.

---

## 11. No Multi-Tenant Support
The system assumes a single logical user environment.

Limitations include:

- No tenant-scoped data partitioning.
- No namespace isolation.
- No tenant-aware ingestion or analytics context.

**Impact:** Would require significant architectural work for SaaS deployment.

---

## 12. No High‑Availability or Scaling Strategy
The system is deployed as a modular monolith using Uvicorn and Vite.

Missing production features:

- Load balancing
- Horizontal scaling
- Auto-scaling of workers
- Distributed caching

**Impact:** Perfect for capstone, not meant for enterprise workloads.

---

## 13. Metrics & Forecast API Do Not Cache Results
All KPI and forecast computations are executed on demand.

**Impact:** Acceptable given dataset size; production systems typically employ caching layers to reduce compute cost.

---

## 14. No UI Accessibility Audit (WCAG)
The frontend UI is functional but:

- No color contrast validation
- No tab-navigation audit
- No ARIA annotation pass

**Impact:** Not critical for the capstone, but necessary for real-world deployment.

---

## 15. Limited Error Message Customization
Backend errors follow FastAPI defaults for:

- Validation errors
- Auth failures
- Internal server errors

---

## Summary
None of the issues above impact the capstone’s required functionality. They represent technical debt and natural constraints of a demo-grade analytics platform. If the system were extended into a production environment, these areas would form the basis of the next set of engineering milestones.
