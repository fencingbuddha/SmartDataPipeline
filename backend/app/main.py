from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.routers import (
    health, upload, kpi, ingest, metrics, sources, anomaly_iforest, forecast
)
from app.schemas.common import ResponseMeta, fail

from typing import Any
import json

app = FastAPI(title="Smart Data Pipeline API")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Meta helper for envelopes ---
def _meta() -> ResponseMeta:
    return ResponseMeta(
        generated_at=datetime.now(timezone.utc).isoformat()
        # version defaults in the model (e.g., "0.7.0")
    )

# --- Global exception handlers (enveloped errors) ---
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException):
    # e.g., 404/401/etc.
    return fail(
        code="HTTP_ERROR",
        message=str(exc.detail),
        status_code=exc.status_code,
        meta=_meta(),
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return fail(
        code="VALIDATION_ERROR",
        message="Invalid request.",
        status_code=422,
        details={"errors": exc.errors()},
        meta=_meta(),
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    return fail(
        code="INTERNAL_SERVER_ERROR",
        message="Unexpected error.",
        status_code=500,
        details={"type": exc.__class__.__name__},
        meta=_meta(),
    )

# --- Routers ---
app.include_router(health.router)
app.include_router(upload.router)
app.include_router(kpi.router)
app.include_router(ingest.router)
app.include_router(metrics.router)
app.include_router(sources.router)
app.include_router(anomaly_iforest.router)
app.include_router(forecast.router)

def _scrub_json(obj: Any, max_len: int = 1000) -> Any:
    """Make validation error structures JSON-serializable (e.g., bytes -> preview string)."""
    if isinstance(obj, (bytes, bytearray)):
        try:
            s = obj.decode("utf-8", errors="replace")
        except Exception:
            s = repr(obj)
        if len(s) > max_len:
            s = s[:max_len] + "... (truncated)"
        return s
    if isinstance(obj, dict):
        return {k: _scrub_json(v, max_len) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub_json(v, max_len) for v in obj]
    try:
        json.dumps(obj)  # check serializable
        return obj
    except Exception:
        return str(obj)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return fail(
        code="VALIDATION_ERROR",
        message="Invalid request.",
        status_code=422,
        details={"errors": _scrub_json(exc.errors())},  # <-- scrubbed
        meta=_meta(),
    )