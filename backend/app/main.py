# app/main.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import router objects explicitly to avoid module name collisions
from app.routers.health import router as health_router
from app.routers.upload import router as upload_router
from app.routers.kpi import router as kpi_router
from app.routers.ingest import router as ingest_router
from app.routers.sources import router as sources_router
from app.routers.forecast import router as forecast_router
from app.routers.anomaly import router as anomaly_router
from app.routers.metrics import router as metrics_router
from app.routers.forecast_reliability import router as forecast_reliability_router
from app.db.session import get_engine
from app.db.base import Base

app = FastAPI(title="Smart Data Pipeline", version="0.7.0")

DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=86400
)

# Ensure tables exist in dev/e2e so the UI and tests don't 500 on brand-new DBs
@app.on_event("startup")
def _ensure_tables() -> None:
    try:
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
    except Exception as ex:  # defensive: don't block startup
        import logging
        logging.getLogger(__name__).exception("Failed to create tables on startup: %s", ex)

# Routers are mounted at import time
app.include_router(health_router)
app.include_router(upload_router)
app.include_router(kpi_router)
app.include_router(ingest_router)
app.include_router(sources_router)
app.include_router(forecast_router)
app.include_router(anomaly_router)
app.include_router(metrics_router)
app.include_router(forecast_reliability_router)
