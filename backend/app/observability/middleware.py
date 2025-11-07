from __future__ import annotations

import time
import uuid
from typing import Any

try:  # pragma: no cover
    import structlog
except ModuleNotFoundError:  # pragma: no cover
    from . import _structlog_stub as structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .metrics import record_latency, REQUEST_COUNTER, REQUEST_LATENCY

logger = structlog.get_logger("http")


async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=str(request.url.path),
        user_agent=request.headers.get("user-agent", "-"),
    )
    try:
        response = await call_next(request)
    except Exception:
        duration = (time.perf_counter() - start) * 1000
        _record(request, duration, "500")
        logger.exception(
            "request.error",
            status_code=500,
            duration_ms=round(duration, 2),
        )
        structlog.contextvars.clear_contextvars()
        raise

    duration = (time.perf_counter() - start) * 1000
    _record(request, duration, str(response.status_code))
    logger.info(
        "request.completed",
        status_code=response.status_code,
        duration_ms=round(duration, 2),
    )
    response.headers["X-Request-Id"] = request_id
    structlog.contextvars.clear_contextvars()
    return response


def _record(request: Request, duration_ms: float, status: str) -> None:
    record_latency(request.url.path, duration_ms)
    REQUEST_COUNTER.labels(
        path=request.url.path,
        method=request.method,
        status=status,
    ).inc()
    REQUEST_LATENCY.labels(path=request.url.path, method=request.method).observe(
        duration_ms / 1000
    )


def register_request_middleware(app: FastAPI) -> None:
    app.middleware("http")(request_context_middleware)


def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger = structlog.get_logger("http")
    logger.exception(
        "request.unhandled_exception",
        exc_type=type(exc).__name__,
        error=str(exc),
    )
    payload: dict[str, Any] = {"detail": "Internal Server Error"}
    if request_id:
        payload["request_id"] = request_id
    return JSONResponse(status_code=500, content=payload)
