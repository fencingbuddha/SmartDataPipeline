from fastapi import FastAPI
from app.routers import health, upload, kpi, ingest, metrics, sources

app = FastAPI(title="Smart Data Pipeline API")

app.include_router(health.router)
app.include_router(upload.router)
app.include_router(kpi.router)
app.include_router(ingest.router)
app.include_router(metrics.router)
app.include_router(sources.router)