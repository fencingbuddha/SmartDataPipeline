from __future__ import annotations

import statistics
from collections import defaultdict, deque
from typing import Deque, Dict, List

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

try:  # pragma: no cover
    from prometheus_client import (
        Counter,
        Histogram,
        CONTENT_TYPE_LATEST,
        generate_latest,
    )
except ModuleNotFoundError:  # pragma: no cover
    from . import _prometheus_stub as prometheus_client  # type: ignore

    Counter = prometheus_client.Counter
    Histogram = prometheus_client.Histogram
    CONTENT_TYPE_LATEST = prometheus_client.CONTENT_TYPE_LATEST
    generate_latest = prometheus_client.generate_latest

router = APIRouter()

REQUEST_COUNTER = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["path", "method", "status"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Request latency",
    ["path", "method"],
)

_LATENCY_SAMPLES: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=200))


def record_latency(path: str, duration_ms: float) -> None:
    _LATENCY_SAMPLES[path].append(duration_ms)


@router.get("/metrics")
async def metrics_endpoint() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/api/health/latency")
async def latency_health() -> dict[str, List[dict[str, float | str]]]:
    payload: List[dict[str, float]] = []
    for path, samples in _LATENCY_SAMPLES.items():
        if not samples:
            continue
        ordered = sorted(samples)
        p50 = _percentile(ordered, 50)
        p95 = _percentile(ordered, 95)
        payload.append({
            "path": path,
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "sample_size": len(samples),
        })
    return {"paths": payload}


def _percentile(ordered: List[float], pct: int) -> float:
    if not ordered:
        return 0.0
    k = (len(ordered) - 1) * (pct / 100)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    d0 = ordered[f] * (c - k)
    d1 = ordered[c] * (k - f)
    return d0 + d1
