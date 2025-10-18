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

app = FastAPI(title="Smart Data Pipeline", version="0.7.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers are mounted at import time
app.include_router(health_router)
app.include_router(upload_router)
app.include_router(kpi_router)
app.include_router(ingest_router)
app.include_router(sources_router)
app.include_router(forecast_router)
app.include_router(anomaly_router)    # /api/anomaly/*
app.include_router(metrics_router)    # /api/metrics/*
