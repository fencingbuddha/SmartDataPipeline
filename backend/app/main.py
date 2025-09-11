from fastapi import FastAPI
from .routers import health, upload, kpi, ingest

app = FastAPI(title="Smart Data Pipeline API")

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(upload.router)
app.include_router(kpi.router, prefix="/kpi", tags=["kpi"])
app.include_router(ingest.router)

@app.get("/health")
def health():
    return {"status": "ok"}