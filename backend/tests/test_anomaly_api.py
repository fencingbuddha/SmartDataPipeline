from __future__ import annotations

from datetime import date
from fastapi.testclient import TestClient
import sqlalchemy as sa

from app.main import app

client = TestClient(app)

def _normalize_anomaly_response(out):
    """
    Accepts either:
      (new) {"points":[{"metric_date":...,"value":...},...],
             "anomalies":[{"metric_date":...,"value":...,"z":...},...], ...}
      (legacy) [{"date": "...", "value": ..., "rolling_mean": ..., "rolling_std": ..., "is_outlier": bool}, ...]
    Returns: (points_list, anomaly_dates_set)
    """
    # New shape
    if isinstance(out, dict) and "points" in out and "anomalies" in out:
        points = out["points"]
        anomaly_dates = {a["metric_date"] for a in out["anomalies"]}
        return points, anomaly_dates

    # Legacy shape
    if isinstance(out, list):
        points = [{"metric_date": r.get("date"), "value": r.get("value")} for r in out]
        anomaly_dates = {r["date"] for r in out if r.get("is_outlier")}
        return points, anomaly_dates

    raise AssertionError(f"Unexpected anomaly response shape: {type(out)} -> {out!r}")


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
    _seed_series_with_spike(db)
    r = client.get(
        "/api/metrics/anomaly/rolling",
        params={
            "source_name": "demo",
            "metric": "events_total",
            "start_date": "2025-09-01",
            "end_date": "2025-09-08",
            "window": 3,
            "z_thresh": 3.0,
            "value_field": "value_sum",
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()

    points, anomaly_dates = _normalize_anomaly_response(out)
    assert len(points) >= 7
    assert "2025-09-06" in anomaly_dates


def test_anomaly_empty_series_is_graceful(db, reset_db):
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
    if isinstance(out, dict):
        assert out["points"] == []
        assert out["anomalies"] == []
    else:
        assert out == []


def test_anomaly_bad_params_rejected(db, reset_db):
    r1 = client.get("/api/metrics/anomaly/rolling",
                    params={"source_name": "demo", "metric": "events_total", "window": 1, "z_thresh": 3.0})
    assert r1.status_code == 422
    r2 = client.get("/api/metrics/anomaly/rolling",
                    params={"source_name": "demo", "metric": "events_total", "window": 5, "z_thresh": -1.0})
    assert r2.status_code == 422


def test_anomaly_empty_series_is_graceful(db, reset_db):
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

    if r.status_code == 404:
        # Your API treats unknown source as a not-found (valid choice).
        data = r.json()
        assert "detail" in data and "Unknown source" in data["detail"]
        return

    # Otherwise, accept the “graceful empty” 200 shape (new or legacy)
    assert r.status_code == 200, r.text
    out = r.json()
    if isinstance(out, dict):
        assert out["points"] == []
        assert out["anomalies"] == []
    else:
        assert out == []  # legacy shape
        

def test_anomaly_bad_params_rejected(db, reset_db):
    r1 = client.get("/api/metrics/anomaly/rolling",
                    params={"source_name": "demo", "metric": "events_total", "window": 1, "z_thresh": 3.0})
    assert r1.status_code == 422
    r2 = client.get("/api/metrics/anomaly/rolling",
                    params={"source_name": "demo", "metric": "events_total", "window": 5, "z_thresh": -1.0})
    assert r2.status_code == 422
