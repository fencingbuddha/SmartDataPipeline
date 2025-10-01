from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import sqlalchemy as sa
from datetime import date, timedelta

# import the router we want to cover directly
from app.routers import anomaly as anomaly_router
from app.db.session import get_db

def _seed_series_with_spike(db):
    db.execute(sa.text("INSERT INTO sources (id, name) VALUES (502, 'unit-demo') ON CONFLICT DO NOTHING"))
    # 5 baseline points + one spike on day 4
    start = date(2025, 9, 1)
    vals = [10, 10, 11, 100, 10, 9]
    for i, v in enumerate(vals):
        d = (start + timedelta(days=i)).isoformat()
        db.execute(
            sa.text("""
                INSERT INTO metric_daily
                  (metric_date, source_id, metric, value_sum, value_avg, value_count, value_distinct)
                VALUES (:d, 502, 'events_total', :v, :v, 1, NULL)
                ON CONFLICT (metric_date, source_id, metric)
                DO UPDATE SET value_sum = EXCLUDED.value_sum,
                              value_avg = EXCLUDED.value_avg,
                              value_count = EXCLUDED.value_count,
                              value_distinct = EXCLUDED.value_distinct
            """),
            {"d": d, "v": float(v)},
        )
    db.commit()

def test_anomaly_router_is_callable_and_flags_spike(db, reset_db):
    # Build a tiny FastAPI just with the anomaly router, and override the DB dep
    app = FastAPI()
    def _override_get_db():
        yield db
    app.dependency_overrides[get_db] = _override_get_db
    app.include_router(anomaly_router.router)

    client = TestClient(app)

    _seed_series_with_spike(db)

    r = client.get(
        "/api/metrics/anomaly/rolling",
        params={
            "source_name": "unit-demo",
            "metric": "events_total",
            "start_date": "2025-09-01",
            "end_date": "2025-09-10",
            "window": 3,
            "z_thresh": 3.0,
            "value_field": "value_sum",
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()

    # Accept new or legacy shapes (reuse helper if you have it; inline here):
    if isinstance(out, dict) and "anomalies" in out:
        anomaly_dates = {a["metric_date"] for a in out["anomalies"]}
    else:
        anomaly_dates = {row["date"] for row in out if row.get("is_outlier")}

    assert "2025-09-04" in anomaly_dates
