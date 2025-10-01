from __future__ import annotations

from fastapi.testclient import TestClient
from datetime import date
import sqlalchemy as sa

from app.main import app

client = TestClient(app)


def _seed_constant_series(db, *, source_id: int, name: str):
    db.execute(sa.text("INSERT INTO sources (id, name) VALUES (:i, :n) ON CONFLICT DO NOTHING"),
               {"i": source_id, "n": name})
    rows = [
        ("2025-09-01", 10), ("2025-09-02", 10),
        ("2025-09-03", 10), ("2025-09-04", 10),
    ]
    for d, v in rows:
        db.execute(
            sa.text("""
                INSERT INTO metric_daily
                  (metric_date, source_id, metric, value_sum, value_avg, value_count, value_distinct)
                VALUES (:d, :sid, 'events_total', :v, :v, 1, NULL)
                ON CONFLICT (metric_date, source_id, metric)
                DO UPDATE SET value_sum=EXCLUDED.value_sum,
                              value_avg=EXCLUDED.value_avg,
                              value_count=EXCLUDED.value_count
            """),
            {"d": d, "sid": source_id, "v": float(v)},
        )
    db.commit()


def _is_empty_payload(out) -> bool:
    if isinstance(out, dict):
        return out.get("points") == [] and out.get("anomalies") == []
    return isinstance(out, list) and len(out) == 0


def test_anomaly_sigma_zero_yields_no_outliers(db, reset_db):
    # Constant series -> rolling stddev becomes zero for many rows; ensure no crash + no anomalies
    _seed_constant_series(db, source_id=910, name="const-demo")
    r = client.get("/api/metrics/anomaly/rolling", params={
        "source_name": "const-demo",
        "metric": "events_total",
        "window": 3,
        "z_thresh": 3.0,
        "value_field": "value_sum",
    })
    assert r.status_code == 200, r.text
    out = r.json()
    if isinstance(out, dict) and "anomalies" in out:
        assert out["anomalies"] == []
    else:
        assert all(not row.get("is_outlier") for row in out)


def test_anomaly_bad_value_field_falls_back_gracefully(db, reset_db):
    _seed_constant_series(db, source_id=911, name="const2")
    # Ask for a non-existent value_field — should still return 200 and a valid shape
    r = client.get("/api/metrics/anomaly/rolling", params={
        "source_name": "const2",
        "metric": "events_total",
        "window": 3,
        "z_thresh": 3.0,
        "value_field": "value_totally_fake",
    })
    assert r.status_code == 200, r.text
    out = r.json()
    assert isinstance(out, (list, dict))


def test_anomaly_known_source_with_no_data_returns_empty(db, reset_db):
    # Known source, but no metric_daily rows -> expect a 200 with empty payload (not 404)
    db.execute(sa.text("INSERT INTO sources (id, name) VALUES (912, 'empty-demo') ON CONFLICT DO NOTHING"))
    db.commit()
    r = client.get("/api/metrics/anomaly/rolling", params={
        "source_name": "empty-demo",
        "metric": "events_total",
        "window": 3,
        "z_thresh": 3.0,
    })
    assert r.status_code == 200, r.text
    assert _is_empty_payload(r.json())
