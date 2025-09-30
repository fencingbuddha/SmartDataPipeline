from __future__ import annotations

from datetime import date
from fastapi.testclient import TestClient
import sqlalchemy as sa

from app.main import app

client = TestClient(app)


def _seed_series_with_spike(db):
    """
    Seed a short series with one obvious spike on 2025-09-06.
    Uses value_sum/value_avg/value_count/value_distinct columns (no plain 'value' column).
    """
    # Ensure source exists (id = 401, name = 'demo')
    db.execute(sa.text(
        "INSERT INTO sources (id, name) VALUES (401, 'demo') ON CONFLICT DO NOTHING"
    ))

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
                    (:d, 401, 'events_total',
                     :v, :v, 1, NULL)
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


def test_anomaly_rolling_flags_spike(db, reset_db):
    """
    Expect the spike on 2025-09-06 to be flagged by rolling z-score (window=3).
    """
    _seed_series_with_spike(db)

    r = client.get(
        "/api/metrics/anomaly/rolling",
        params={
            "source_name": "demo",
            "metric": "events_total",
            "start_date": "2025-09-01",
            "end_date": "2025-09-08",
            "window": 3,          # use prior 3 points to compute mean/stddev
            "z_thresh": 3.0,      # strict threshold
            "value_field": "value_sum",
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()

    # New response shape: {"points": [...], "anomalies": [...], "window": ..., ...}
    assert isinstance(out, dict) and "points" in out and "anomalies" in out
    assert len(out["points"]) >= 7

    anomaly_dates = {a["metric_date"] for a in out["anomalies"]}
    assert "2025-09-06" in anomaly_dates, f"Spike date missing. Got anomalies at: {sorted(anomaly_dates)}"


def test_anomaly_empty_series_is_graceful(db, reset_db):
    """
    Unknown source returns 200 with empty arrays (graceful for UI).
    """
    r = client.get(
        "/api/metrics/anomaly/rolling",
        params={
            "source_name": "no-such-source",
            "metric": "events_total",
            "start_date": "2025-09-01",
            "end_date": "2025-09-08",
            "window": 3,
            "z_thresh": 3.0,
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["points"] == []
    assert out["anomalies"] == []


def test_anomaly_bad_params_rejected(db, reset_db):
    """
    FastAPI validation should reject invalid params.
    """
    r1 = client.get(
        "/api/metrics/anomaly/rolling",
        params={
            "source_name": "demo",
            "metric": "events_total",
            "window": 1,      # too small (ge=2)
            "z_thresh": 3.0,
        },
    )
    assert r1.status_code == 422

    r2 = client.get(
        "/api/metrics/anomaly/rolling",
        params={
            "source_name": "demo",
            "metric": "events_total",
            "window": 5,
            "z_thresh": -1.0,  # must be > 0
        },
    )
    assert r2.status_code == 422
