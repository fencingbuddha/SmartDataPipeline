# Smart Data Pipeline & Dashboard

![CI](https://github.com/fencingbuddha/SmartDataPipeline/actions/workflows/ci.yml/badge.svg?branch=main)

**CSV/JSON → ETL → KPIs → Anomalies → Forecasts → Interactive Dashboard**

A lightweight analytics platform that ingests raw datasets, automates KPI calculation, detects anomalies, forecasts trends, and visualizes results in a React dashboard.  
Built with **FastAPI**, **React**, **PostgreSQL/SQLite**, **APScheduler**, and **SARIMAX**.

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
For the capstone demo and grading environment, the backend defaults to SQLite (Smartdata.db), while PostgreSQL remains supported for future production style deployments. 

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
cd backend
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
