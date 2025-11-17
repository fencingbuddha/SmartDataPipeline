from __future__ import annotations

import pytest
import httpx
import sqlalchemy as sa

from app.main import app
from app.db.session import get_db


def _override_db_dep(db):
    # Ensure the router uses the test session inside ASGI transport
    app.dependency_overrides[get_db] = lambda: db


def _seed_series_with_spike(db):
    """
    Seed a short series with one obvious spike on 2025-09-06.
    Uses value_sum/value_avg/value_count/value_distinct columns (no plain 'value').
    """
    # Ensure source exists (id = 902, name = 'httpx-demo')
    db.execute(sa.text("INSERT INTO sources (id, name) VALUES (902, 'httpx-demo') ON CONFLICT DO NOTHING"))

    rows = [
        ("2025-09-01", 10), ("2025-09-02", 11), ("2025-09-03", 9),
        ("2025-09-04", 10), ("2025-09-05", 10), ("2025-09-06", 100),  # spike
        ("2025-09-07", 10),
    ]
    for d, v in rows:
        db.execute(sa.text("""
            INSERT INTO metric_daily
                (metric_date, source_id, metric,
                 value_sum, value_avg, value_count, value_distinct)
            VALUES
                (:d, 902, 'events_total',
                 :v, :v, 1, NULL)
            ON CONFLICT (metric_date, source_id, metric)
            DO UPDATE SET
                value_sum = EXCLUDED.value_sum,
                value_avg = EXCLUDED.value_avg,
                value_count = EXCLUDED.value_count,
                value_distinct = EXCLUDED.value_distinct
        """), {"d": d, "v": float(v)})
    db.commit()


def _normalize_anomaly_response(out):
    """
    Accept both shapes:
      - enveloped: {"ok":..., "data": {"points":[...], ["anomalies":[...]]}}
      - new: {"points":[...], "anomalies":[...]}
      - points-only: {"points":[...]}  (infer anomalies from is_outlier)
      - legacy: [ {"date":..., "is_outlier":...}, ... ]
    Returns (points_len, anomaly_dates_set).
    """
    if isinstance(out, dict) and "ok" in out and "data" in out:
        out = out["data"] or {}

    if isinstance(out, dict) and "points" in out and "anomalies" in out:
        anomalies = {a.get("metric_date") for a in out.get("anomalies", []) if a.get("metric_date")}
        return len(out.get("points", [])), anomalies

    if isinstance(out, dict) and "points" in out:
        pts = out.get("points", [])
        anomalies = {p.get("date") for p in pts if isinstance(p, dict) and p.get("is_outlier")}
        return len(pts), anomalies

    if isinstance(out, list):
        anomalies = {r.get("date") for r in out if isinstance(r, dict) and r.get("is_outlier")}
        return len(out), anomalies

    raise AssertionError(f"Unexpected response shape: {type(out)} -> {out!r}")


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])  # force asyncio; avoid trio run
async def test_anomaly_httpx_happy(anyio_backend, db, reset_db):
    _override_db_dep(db)
    _seed_series_with_spike(db)

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get(
                "/api/metrics/anomaly/rolling",
                params=dict(
                    source_name="httpx-demo",
                    metric="events_total",
                    start_date="2025-09-01",
                    end_date="2025-09-08",
                    window=3,
                    z_thresh=3.0,
                    value_field="value_sum",  # harmless if ignored
                ),
            )
            assert r.status_code == 200, r.text
            points_len, anomaly_dates = _normalize_anomaly_response(r.json())
            assert points_len >= 7
            assert "2025-09-06" in anomaly_dates
    finally:
        app.dependency_overrides.pop(get_db, None)
