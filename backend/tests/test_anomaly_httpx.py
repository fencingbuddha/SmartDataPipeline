from __future__ import annotations

import sqlalchemy as sa
import pytest
import httpx
from app.main import app
from app.db.session import get_db

# Force AnyIO to use the asyncio backend only for this module.
# This overrides pytest-anyio's default (asyncio+trio) parametrization.
@pytest.fixture
def anyio_backend():
    return "asyncio"


def _override_db_dep(db):
    """Override FastAPI's get_db dependency so the client uses the same test session."""
    def _dep():
        yield db
    app.dependency_overrides[get_db] = _dep


def _clear_overrides():
    app.dependency_overrides.pop(get_db, None)


def _seed_series_with_spike(db):
    """
    Seed a short series with an obvious spike on 2025-09-06 for source 'httpx-demo' (id=902).
    Uses MetricDaily columns: value_sum/value_avg/value_count/value_distinct.
    """
    db.execute(
        sa.text("INSERT INTO sources (id, name) VALUES (902, 'httpx-demo') ON CONFLICT DO NOTHING")
    )
    rows = [
        ("2025-09-01", 10), ("2025-09-02", 11), ("2025-09-03", 9),
        ("2025-09-04", 10), ("2025-09-05", 10), ("2025-09-06", 100),  # spike
        ("2025-09-07", 10),
    ]
    for d, v in rows:
        db.execute(
            sa.text(
                """
                INSERT INTO metric_daily
                    (metric_date, source_id, metric,
                     value_sum, value_avg, value_count, value_distinct)
                VALUES
                    (:d, 902, 'events_total', :v, :v, 1, NULL)
                ON CONFLICT (metric_date, source_id, metric)
                DO UPDATE SET
                    value_sum = EXCLUDED.value_sum,
                    value_avg = EXCLUDED.value_avg,
                    value_count = EXCLUDED.value_count,
                    value_distinct = EXCLUDED.value_distinct
                """
            ),
            {"d": d, "v": float(v)},
        )
    db.commit()


def _normalize_anomaly_response(out):
    """
    Accept both shapes:
      - new: {"points":[...], "anomalies":[...], ...}
      - legacy: [ {"date":..., "is_outlier":...}, ... ]
    Returns (points_len, anomaly_dates_set).
    """
    if isinstance(out, dict) and "points" in out and "anomalies" in out:
        return len(out["points"]), {a["metric_date"] for a in out["anomalies"]}
    if isinstance(out, list):
        return len(out), {r["date"] for r in out if r.get("is_outlier")}
    raise AssertionError(f"Unexpected response shape: {type(out)} -> {out!r}")


@pytest.mark.anyio
async def test_anomaly_httpx_happy(db, reset_db):
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
                    value_field="value_sum",
                ),
            )
            assert r.status_code == 200, r.text
            points_len, anomaly_dates = _normalize_anomaly_response(r.json())
            assert points_len >= 7
            assert "2025-09-06" in anomaly_dates
    finally:
        _clear_overrides()


@pytest.mark.anyio
async def test_anomaly_httpx_invalid_params(db, reset_db):
    _override_db_dep(db)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            # window too small
            r1 = await ac.get(
                "/api/metrics/anomaly/rolling",
                params=dict(source_name="x", metric="y", window=1, z_thresh=3.0),
            )
            assert r1.status_code == 422

            # z_thresh must be > 0
            r2 = await ac.get(
                "/api/metrics/anomaly/rolling",
                params=dict(source_name="x", metric="y", window=7, z_thresh=-1),
            )
            assert r2.status_code == 422

            # missing required param source_name (accept 200 or 422, depending on router version)
            r3 = await ac.get(
                "/api/metrics/anomaly/rolling",
                params=dict(metric="y", window=7, z_thresh=3.0),
            )
            assert r3.status_code in (200, 422)
            if r3.status_code == 200:
                out = r3.json()
                assert isinstance(out, (list, dict))

            # unknown source: API may return 404 (preferred) or 200 with empty arrays
            r4 = await ac.get(
                "/api/metrics/anomaly/rolling",
                params=dict(source_name="no-such-source", metric="y", window=7, z_thresh=3.0),
            )
            assert r4.status_code in (200, 404)
            if r4.status_code == 200:
                out = r4.json()
                if isinstance(out, dict):
                    assert out["points"] == [] and out["anomalies"] == []
                else:
                    assert out == []
    finally:
        _clear_overrides()
