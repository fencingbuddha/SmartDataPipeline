# Smart Data Pipeline & Dashboard

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

## 🌱 Environment

- `DATABASE_URL` (dev/test), e.g.  
  `postgresql+psycopg2://postgres:postgres@localhost:5433/smartdata_test`

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

GitHub Actions runs:

✅ Linting

✅ Tests

✅ Frontend build

Workflow: .github/workflows/ci.yml

📊 Agile Board

Backlogs managed in GitHub Projects:

Sprint 1: Upload, ETL, KPIs, basic dashboard, error handling

Sprint 2: Anomalies, forecasting, filters, performance/reliability

Sprint 3: Exports, auth, logging, accessibility/security

Sprint 4: Scheduler, maintainability, portability, docs, risks

🔐 Non-Functional Targets

Performance: ≤10 MB ingest in ≤5s @ P95

Reliability: ≥99% uptime during evaluation

Accessibility: WCAG 2.1 AA compliance

Security: TLS 1.2+, encryption at rest

Maintainability: ≥70% test coverage

Portability: ZIP release with SQLite runtime

📜 License
MIT © 2025 Cameron Beebe
