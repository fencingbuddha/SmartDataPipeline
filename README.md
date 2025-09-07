# SmartDataPipeline

**CSV/JSON in → Clean data → KPIs → anomalies → forecasts → beautiful charts.**  
Built with **FastAPI** + **React** + **PostgreSQL/SQLite** + **APScheduler** + **statsmodels (SARIMAX)**.

[![CI](https://img.shields.io/badge/CI-GitHub_Actions-blue)](#-ci--automation)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Made with FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![Made with React](https://img.shields.io/badge/frontend-React-61DAFB)](https://react.dev/)

---

## ✨ What it does (MVP)

- **Upload** CSV/JSON
- **ETL pipeline**: parse → validate → normalize to `CleanEvents`
- **Daily KPIs** → `MetricDaily`
- **Anomaly detection**: rolling **z-score** + **Isolation Forest** → `Alerts`
- **Forecasting**: **SARIMAX** → `ForecastResults`
- **React dashboard**: charts, filters, export **PNG/CSV**
- **Scheduler** (APScheduler): nightly KPIs, weekly retraining, cleanup
- **Auth + logging** (scoped for MVP)
- **Portability**: ZIP release with **SQLite** (no external deps required to run)

> Performance target: **≤10 MB file ingested in ≤5s @ P95** (stretch goal).

---

## 🏗️ Architecture (3-tier + pipe-and-filter)


