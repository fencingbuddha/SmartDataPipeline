from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import health, upload, kpi, ingest, metrics, sources

app = FastAPI(title="Smart Data Pipeline API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(upload.router)
app.include_router(kpi.router)
app.include_router(ingest.router)
app.include_router(metrics.router)
app.include_router(sources.router)
