# Smart Data Pipeline — Test Strategy

## 1. Purpose
This document defines the overall testing strategy for the Smart Data Pipeline project. It establishes the testing goals, scope, methodologies, environments, responsibilities, and acceptance criteria required to validate all functional and non-functional requirements. The strategy applies to the backend (FastAPI services), the frontend (React dashboard), and the portable release (SQLite + scripts).

---

## 2. Testing Goals
- Verify correctness of all ingestion, KPI, anomaly, forecasting, and scheduling workflows.
- Validate non‑functional requirements including performance, security (QR‑4), portability (QR‑6), and maintainability (QR‑5).
- Ensure the system behaves consistently in both PostgreSQL (dev/test) and SQLite (portable) environments.
- Provide measurable evidence through automated tests, coverage, logs, and artifacts.

---

## 3. Test Types & Scope

### 3.1 Unit Testing
Focus: smallest testable units in isolation.  
Coverage areas:
- Services (ETL, KPI calculation, anomaly scoring, SARIMAX fallback logic)
- Utilities (numeric helpers, envelope formatting, crypto functions)
- Security middleware and header validation

Tools: `pytest`, `pytest-anyio`, `pytest-cov`.

### 3.2 Integration Testing
Focus: multi-component workflows with the app running against the test database.  
Scope:
- Raw ingestion → Clean events → KPI aggregation
- Anomaly detection endpoints
- Forecasting pipeline and contracts
- Authentication flows

Tools: FastAPI TestClient, PostgreSQL test DB.

### 3.3 System Testing (End-to-End API Testing)
Focus: full application behavior through its public API surface.  
Scope:
- Route validation
- Error contracts
- Cross-service interaction
- Scheduler job registration and execution

### 3.4 User Acceptance Testing (UAT)
Focus: requirements-level validation.  
Scope:
- Ingestion uploads
- KPI daily retrieval
- Forecast daily output contracts
- Anomaly overlays
- Auth success + invalid-token behavior

Evidence: UAT tests in `tests/uat/`.

### 3.5 Security Testing
Scope:
- JWT authentication (login, refresh, expiry)
- Security headers
- Hardened CSP configuration
- Malformed input handling

Tools: Automated pytest + Bandit + pip-audit.

### 3.6 Performance & Reliability Testing
Scope:
- Ingestion of large CSVs
- SARIMAX fallback analysis (FR‑13)
- Scheduler-backed reliability score recalculation
- KPI batching

Approach: synthetic datasets + performance logs.

### 3.7 Portability Testing
Focus: QR‑6 demo ZIP running correctly on macOS, Linux, and Windows.  
Validations:
- `start_all.sh` and `start_all.ps1` scripts
- SQLite migrations
- Authentication and dashboard access
- Ingestion + KPI + forecast flows

---

## 4. Test Environments

### 4.1 Local Dev Environment
- Python 3.11–3.14
- FastAPI auto-reload
- PostgreSQL or SQLite
- Frontend served via Vite (for manual E2E)

### 4.2 Automated Test Environment
- GitHub Actions CI
- PostgreSQL service container
- Full unit + integration + UAT test suite
- Security scanning (Bandit, pip‑audit)

### 4.3 Portable Release Environment
- SQLite runtime
- Setup + start scripts
- Smoke tests run manually

---

## 5. Test Data Strategy
- Synthetic JSON/CSV files for ingestion testing
- Boundary datasets to trigger SARIMAX fallback
- Large data files (~10k rows) for stress testing
- Static datasets for reproducible forecasting

---

## 6. Acceptance Criteria
A feature is considered complete when:
- All requirement‑mapped tests pass
- No regressions are introduced
- Coverage remains ≥80%
- Logs do not show unhandled exceptions
- Swagger contract is satisfied
- UAT demonstrates compliance with functional requirements

---

## 7. Defect Categorization
**Critical:** prevents ingestion, KPI computation, or forecast generation.  
**High:** breaks API contract but system remains partially functional.  
**Medium:** incorrect formatting, incomplete branches, minor inconsistencies.  
**Low:** cosmetic or non-blocking issues documented in known-issues.md.

---

## 8. Traceability
Each test maps to:
- A specific FR/QR requirement
- One or more commits
- A corresponding module or router
- Evidence captured in coverage reports, logs, and artifacts

Formal traceability matrix lives in `docs/testing/traceability-matrix.md`.

---

## 9. Maintenance Plan
- Update tests with each new requirement (FR/QR)
- Expand coverage for new routers/services
- Remove deprecated modules (e.g., legacy DB helpers) as part of QR‑5 maintainability
- Add reliability and forecasting robustness tests as models evolve

---

## 10. Conclusion
This strategy ensures that Smart Data Pipeline is validated at every layer—from unit functions to full-stack workflows, from security to portability. Combined with >84% test coverage and extensive automated UAT, the application meets all requirements for correctness, reliability, security hardening, and demo readiness.
