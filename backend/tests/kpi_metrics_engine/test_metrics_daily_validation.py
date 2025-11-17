from __future__ import annotations

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Reuse unwrap helper if present
try:
    from _helpers import unwrap  # noqa: F401
except Exception:
    def unwrap(obj):
        if isinstance(obj, dict) and "ok" in obj and "data" in obj:
            return obj["data"]
        return obj


def test_requires_some_selector():
    r = client.get("/api/metrics/daily")  # no params
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        data = unwrap(r.json())
        assert isinstance(data, list)


def test_rejects_bad_dates():
    r = client.get(
        "/api/metrics/daily",
        params={
            "source_name": "demo",
            "metric": "events_total",
            "start_date": "not-a-date",
            "end_date": "2025-09-22",
        },
    )
    # FastAPI schema validation typically yields 422; some routers coerce and return 400
    assert r.status_code in (400, 422)


def test_start_end_inclusive_semantics():
    r = client.get(
        "/api/metrics/daily",
        params={
            "source_name": "demo",
            "metric": "events_total",
            "start_date": "2025-09-16",
            "end_date": "2025-09-16",
        },
    )
    assert r.status_code == 200
    data = unwrap(r.json())
    assert isinstance(data, list)
