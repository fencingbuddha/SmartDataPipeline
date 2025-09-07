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

[ React SPA ] → [ FastAPI Service ] → [ PostgreSQL (dev) / SQLite (release) ]

FastAPI modules:
• ETL Pipeline
• KPI Calculator
• Anomaly Detector
• Forecasting Engine
• Scheduler (APScheduler)
• Auth
• Logging/Monitoring


Deployment: modular monolith for simplicity, split-ready later.

---

## 📂 Project Structure
SmartDataPipeline/
├─ backend/
│ ├─ app.py # FastAPI entrypoint
│ ├─ api/ # routers (upload, kpis, anomalies, forecasts, auth)
│ ├─ services/ # etl, kpi, anomaly, forecast, scheduler
│ ├─ models/ # SQLAlchemy models
│ ├─ db/ # db session, migrations
│ ├─ tests/ # pytest suites
│ └─ requirements.txt
├─ frontend/
│ ├─ src/ # React app (components, pages, api client)
│ └─ package.json
├─ docs/ # architecture diagrams, risks.md, notes
├─ .github/workflows/ci.yml # GitHub Actions CI pipeline
└─ README.md


---

🚀 Getting Started

Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL (dev) / SQLite (release)

1. Clone & setup environment
```bash
git clone https://github.com/<your-username>/SmartDataPipeline.git
cd SmartDataPipeline
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
```
2. Backend (FastAPI)
cd backend
cp .env.example .env
uvicorn app:app --reload
Docs: http://localhost:8000/docs

3. Frontend (React)
cd frontend
npm install
npm run dev
Dashboard: http://localhost:5173

🧪 Testing
pytest -q

Covers:

ETL transforms

KPI aggregations

Anomaly thresholds

Forecast reproducibility

♻️ CI/CD

GitHub Actions runs:

✅ Linting
✅ Tests
✅ Frontend build

Workflow: .github/workflows/ci.yml

📊 Agile Board
Product & Sprint Backlogs are managed in GitHub Projects:
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
