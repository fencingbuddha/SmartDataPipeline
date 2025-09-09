from fastapi import FastAPI
from .routers import health, upload, kpi

app = FastAPI(title="Smart Data Pipeline API")
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(upload.router, prefix="/upload", tags=["upload"])
app.include_router(kpi.router,    prefix="/kpi",    tags=["kpi"])
