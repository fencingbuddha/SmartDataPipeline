# Smart Data Pipeline & Dashboard

![CI](https://github.com/fencingbuddha/SmartDataPipeline/actions/workflows/ci.yml/badge.svg?branch=main)

**CSV/JSON → ETL → KPIs → Anomalies → Forecasts → Interactive Dashboard**

A lightweight analytics platform that ingests raw datasets, automates KPI calculation, detects anomalies, forecasts trends, and visualizes results in a React dashboard.  
Built with **FastAPI**, **React**, **PostgreSQL/SQLite**, **APScheduler**, and **SARIMAX**.

---

## ✨ Features

- 📂 Upload CSV/JSON files  
- 🧹 ETL pipeline → normalize into `CleanEvents`  
- 📊 Daily KPIs → stored in `MetricDaily`  
- 🚨 Anomaly detection → rolling z-scores + Isolation Forest  
- 🔮 Forecasting → SARIMAX models  
- 🖥️ React dashboard for KPIs, anomalies, forecasts  
- 🎛️ Filters by date, source, metric type  
- 📤 Export charts & KPIs to PNG/CSV  
- ⏱️ Scheduler (APScheduler) for nightly jobs & weekly retraining  
- 🔐 Authentication for dashboard access  
- 📜 Logging & monitoring for metrics, alerts, errors  
- ✅ Portable ZIP release with SQLite runtime  

---

## 🏗️ Architecture

The system follows a **3-tier client–server architecture** with **pipe-and-filter ETL** and **event-driven scheduling**.

`[ React SPA ] → [ FastAPI Service ] → [ PostgreSQL (dev) / SQLite (release) ]`

FastAPI modules:
- ETL Pipeline
- KPI Calculator
- Anomaly Detector
- Forecasting Engine
- Scheduler (APScheduler)
- Auth
- Logging/Monitoring

Deployment: modular monolith for simplicity, split-ready later.

---

## 📂 Project Structure
SmartDataPipeline/
├── README.md
├── requirements.txt
      └── backend/
├── alembic.ini
├── pytest.ini
├── requirements.txt
├── scripts/
│     └── init_db.sql
├── migrations/
│      ├── env.py
│      ├── script.py.mako
│      └── versions/
│             ├── 7ba82119ad85_create_sources_and_raw_events.py
│             ├── 97c813a0e571_add_metric_daily_indexes.py
│             └── beaed7f34243_add_metricdaily_table.py
└── app/
├── main.py
├── config.py
├── db/
│     ├── base.py
│     └── session.py
├── models/
│     ├── clean_event.py
│     ├── metric_daily.py
│     ├── raw_event.py
│     └── source.py
├── routers/
│     ├── health.py
│     ├── ingest.py
│     ├── kpi.py
│     └── upload.py
└── services/
    ├── ingestion.py
    └── kpi.py
    └── tests/
    ├── conftest.py
    ├── test_ingestion_api.py
    ├── test_kpi.py
    └── test_upload.py

---

## 🌱 Environment & Secrets

- `DATABASE_URL` (dev/test), e.g.  
  `postgresql+psycopg2://postgres:postgres@localhost:5433/smartdata_test`
- `DB_APP_ROLE` → expected Postgres runtime role (defaults to none; set to `sdp_app` in prod).
- `DB_REQUIRE_SSL` → keep `true` in prod so the driver forces `sslmode=require` (set to `false` only for local labs without TLS).
- `FORCE_HTTPS`, `TRUSTED_HOSTS`, `CONTENT_SECURITY_POLICY` → hardened FastAPI networking.
- `APP_ENCRYPTION_KEY` → Fernet key used to encrypt `raw_events.payload` before the database ever sees it.

**Production deployments:** store every secret above (plus JWT + API keys) in your secret manager (GitHub Environment secrets, AWS/GCP Secret Manager, etc.) and use GitHub OIDC when CI assumes deploy roles. `.env` files are local-only.

---

## 🗃️ Databases: Dev vs Test (and `.env`)

This project uses **two Postgres databases** so development and tests don’t step on each other:

- **Dev (runtime app):** `DATABASE_URL` → typically `.../smartdata`
- **Test (pytest only):** `TEST_DATABASE_URL` → typically `.../smartdata_test`

Create `backend/.env` (adjust port/creds if yours differ, e.g. 5432 vs 5433):

```ini
ENV=dev
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/smartdata
TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/smartdata_test
```
---

## 🚀 Getting Started

**Prerequisites**
- Python 3.11+
- Node.js 18+ (for the frontend, if used)
- PostgreSQL (dev) / SQLite (release)

**1) Clone & setup**
```bash
git clone https://github.com/<your-username>/SmartDataPipeline.git
cd SmartDataPipeline
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```
2) Backend (FastAPI)

cd backend
cp .env.example .env
uvicorn app.main:app --reload
# Docs:
# http://localhost:8000/docs


3) Frontend (React)

cd frontend
npm install
npm run dev
# Dashboard:
# http://localhost:5173

## 🚀 Production Deployment (secure)

1. Run [`infra/db/roles.sql`](./infra/db/roles.sql) against your managed Postgres instance to create `sdp_migrations`, `sdp_app`, and (optionally) `sdp_readonly`.
2. Store the following secrets in your vault (GitHub environment secrets, AWS/GCP Secret Manager, 1Password, etc.): `DATABASE_URL` (runtime role), `MIGRATION_DATABASE_URL`, `JWT_SECRET`, `APP_ENCRYPTION_KEY`, API keys, and any third-party credentials. Configure your GitHub Actions environment to retrieve them via OIDC (no long-lived cloud keys).
3. Configure your CDN / reverse proxy for HTTPS-only traffic, TLS ≥ 1.2, and HSTS. Set `FORCE_HTTPS=true`, `TRUSTED_HOSTS=<your domains>`, and ensure the backend CSP matches your frontend origin.
4. Deploy the backend (`uvicorn`/container) and frontend, run `pytest` plus the CI security job locally if needed.
5. Capture evidence (`curl -Ik https://<host>/health` and `openssl s_client -connect <host>:443 -tls1_2 </dev/null`) and attach it to the release PR titled **`feat(qr4): security hardening`**.

Refer to [SECURITY.md](./SECURITY.md) for the full runbook, rotation policy, and disclosure process.

📥 Ingestion Usage

Endpoint
POST /api/ingest?source_name={name}

CSV (multipart)

curl -s -X POST \
  -F "file=@data.csv;type=text/csv" \
  "http://127.0.0.1:8000/api/ingest?source_name=demo"


JSON (raw body)

curl -s -X POST \
  -H "Content-Type: application/json" \
  --data-binary @data.json \
  "http://127.0.0.1:8000/api/ingest?source_name=demo"


Response

{
  "source": "demo",
  "inserted": 2,
  "duplicates": 0,
  "raw_events_inserted": 2,
  "clean_events_inserted": 2
}


Errors

400: invalid schema/value (strict validation; entire request is rolled back)

415: unsupported media type

🧪 Testing

Run tests:

cd backend
pytest -q


With coverage:

pytest -q --cov=app/services --cov-report=term-missing

♻️ CI/CD

GitHub Actions jobs (see `.github/workflows/ci.yml`):

- ✅ Backend unit tests (FastAPI + Postgres service)
- ✅ Frontend build/tests
- ✅ **Security** job: `pip-audit`, `bandit`, `npm audit --omit=dev`, and ESLint in `--max-warnings=0` mode. Treat failures as blocking.

Deployments should consume GitHub OIDC tokens instead of static cloud keys. See [SECURITY.md](./SECURITY.md) for the full checklist.

📊 Agile Board

Backlogs managed in GitHub Projects:

Sprint 1: Upload, ETL, KPIs, basic dashboard, error handling

Sprint 2: Anomalies, forecasting, filters, performance/reliability

Sprint 3: Exports, auth, logging, accessibility/security

Sprint 4: Scheduler, maintainability, portability, docs, risks

🔐 Security Hardening Checklist

| Control | How |
| --- | --- |
| HTTPS-only + HSTS | Enable redirects on your CDN/LB, set `FORCE_HTTPS=true`, record `curl -Ik https://<host>/health` output in PRs |
| TLS 1.2+ evidence | Attach `openssl s_client -connect <host>:443 -tls1_2 </dev/null` output to your release PR |
| Security headers + CSP | Enabled by default via `SecurityHeadersMiddleware`; override with `CONTENT_SECURITY_POLICY` as needed |
| Database least privilege | Apply [`infra/db/roles.sql`](./infra/db/roles.sql), set `DB_APP_ROLE=sdp_app`, point Alembic/migrations at `sdp_migrations` |
| DB encryption | Managed Postgres already encrypts at rest; local dev must use FileVault/APFS or SQLCipher. `DB_REQUIRE_SSL=true` enforces TLS in flight. |
| App-layer encryption | `raw_events.payload` is encrypted with Fernet (`APP_ENCRYPTION_KEY`). Rotate the key via your secret manager. |
| Secrets | Move DB URLs, JWTs, encryption keys, API keys into GitHub Environment secrets or your cloud Secret Manager. Document rotations in PRs. |
| CI security job | Automatically runs in GitHub Actions; do not merge if it fails. |

When filing the QR-4 security PR, title it **`feat(qr4): security hardening`**, paste the checklist above in the PR body, and attach the `curl`/`openssl` evidence. See [SECURITY.md](./SECURITY.md) for the expanded runbook (OIDC deploys, rotation process, disclosure policy).

📜 License
MIT © 2025 Cameron Beebe

# Smart Data Pipeline & Dashboard
**FastAPI + React + SQLite/PostgreSQL + ETL + KPIs + Anomalies + Forecasts + Scheduler**

![CI](https://github.com/fencingbuddha/SmartDataPipeline/actions/workflows/ci.yml/badge.svg?branch=main)

A full-stack analytics platform that ingests raw event data (CSV/JSON), processes it through an ETL pipeline, computes KPIs, detects anomalies, forecasts trends, and displays insights in a smooth, interactive dashboard.

---

## ✨ Core Capabilities

### 🔄 Data Ingestion & ETL
- CSV/JSON upload
- Schema validation
- Raw → Clean → Metrics transformation
- Duplicate protection (idempotent ingestion)

### 📊 Analytics Engine
- Daily KPIs stored in `MetricDaily`
- Rolling Z-score anomaly detection
- Isolation Forest anomaly models
- SARIMAX forecasting (with fallback constant model)
- Reliability scoring (MAPE-based)

### 🖥️ Dashboard (React + Vite)
- Charting: KPIs, anomalies, forecast ranges
- Filtering by date, source, and metric
- Export: PNG + CSV
- Reliability badge indicators
- JWT-based authentication (login/refresh flow)

### ⚙️ Backend (FastAPI)
- Modular service architecture
- Auth, ETL, KPI, Forecast, Anomaly routers
- APScheduler nightly jobs + weekly retraining
- Security headers & CORS
- Structured logging (FR-11)

### 📦 Portability (QR-6)
- Portable ZIP release
- Automated setup scripts
- SQLite runtime
- macOS/Linux/Windows support
- Zero external dependencies

---

## 🏗️ Architecture
```
[ React Frontend ] → [ FastAPI Backend ] → [ PostgreSQL (dev) / SQLite (portable release) ]
```

Key backend domains:
- `ingest` — upload + raw ingestion
- `kpi` — metrics pipeline
- `anomaly` — Z-score + Isolation Forest
- `forecast` — SARIMAX engine
- `reliability` — scoring model
- `auth` — JWT access + refresh
- `scheduler` — job orchestration

---

## 📂 Project Structure (Updated)
```
SmartDataPipeline/
│
├── README.md
├── README_PORTABLE.md
├── env/
│   ├── backend.env.example
│   └── frontend.env.example
│
├── scripts/
│   ├── setup_backend.sh
│   ├── setup_frontend.sh
│   ├── start_all.sh
│   ├── start_all.ps1
│   └── build_portable_zip.sh
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── routers/
│   │   ├── services/
│   │   ├── schemas/
│   │   ├── utils/
│   │   └── scheduler/
│   ├── migrations/
│   └── tests/
│
└── frontend/
    ├── src/
    ├── public/
    └── cypress/
```

---

## 🚀 Local Development

### Backend
```bash
dcd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../env/backend.env.example .env
uvicorn app.main:app --reload
```
Swagger (auth-limited): http://localhost:8000/docs

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Dashboard: http://localhost:5173

---

## 🧪 Testing

### Backend
```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

### Frontend
```bash
cd frontend
npx cypress run
```

---

## 📦 Portable Release (QR-6)

Build a portable demo ZIP:
```bash
./scripts/build_portable_zip.sh
```
Run the portable demo:
```bash
./scripts/start_all.sh
```
Windows:
```powershell
scripts/start_all.ps1
```
Full instructions: see **README_PORTABLE.md**

---

## 🔐 Security
- HTTPS enforcement
- TLS 1.2+ compliance
- Postgres role separation (`sdp_migrations`, `sdp_app`, `sdp_readonly`)
- App-layer encryption (Fernet)
- Strict security middleware
- CI: Bandit, pip-audit, npm audit, ESLint strict mode

Details: **SECURITY.md**

---

## 📊 Agile Development
- **Sprint 1:** Upload, ETL, KPIs, initial UI
- **Sprint 2:** Anomalies, forecasting, filters, perf
- **Sprint 3:** Exports, auth, logging, accessibility, QR-4 security
- **Sprint 4:** Scheduler, maintainability, portability, docs, risks

---

## 📜 License
MIT © 2025 Cameron Beebe