from __future__ import annotations

from fastapi.testclient import TestClient
import sqlalchemy as sa

from app.main import app

client = TestClient(app)

# Reuse helpers
try:
    from _helpers import unwrap  # noqa
except Exception:  # fallback if helpers aren't present
    def unwrap(obj):
        if isinstance(obj, dict) and "ok" in obj and "data" in obj:
            return obj["data"]
        return obj


def _seed_constant_series(db, *, source_id=910, name="const-demo"):
    """
    Seed a constant series (stddev == 0) so rolling anomaly should not flag anything.
    Uses value_sum/value_avg/value_count columns.
    """
    db.execute(sa.text("INSERT INTO sources (id, name) VALUES (:id, :name) ON CONFLICT DO NOTHING"),
               {"id": source_id, "name": name})

    rows = [
        ("2025-09-01", 10), ("2025-09-02", 10), ("2025-09-03", 10),
        ("2025-09-04", 10), ("2025-09-05", 10), ("2025-09-06", 10),
        ("2025-09-07", 10),
    ]
    for d, v in rows:
        db.execute(sa.text("""
            INSERT INTO metric_daily
                (metric_date, source_id, metric,
                 value_sum, value_avg, value_count, value_distinct)
            VALUES
                (:d, :sid, 'events_total',
                 :v, :v, 1, NULL)
            ON CONFLICT (metric_date, source_id, metric)
            DO UPDATE SET
                value_sum = EXCLUDED.value_sum,
                value_avg = EXCLUDED.value_avg,
                value_count = EXCLUDED.value_count,
                value_distinct = EXCLUDED.value_distinct
        """), {"d": d, "sid": source_id, "v": float(v)})
    db.commit()


def test_anomaly_sigma_zero_yields_no_outliers(db, reset_db):
    _seed_constant_series(db, source_id=910, name="const-demo")
    r = client.get("/api/metrics/anomaly/rolling", params={
        "source_name": "const-demo",
        "metric": "events_total",
        "window": 3,
        "z_thresh": 3.0,
        "value_field": "value_sum",  # harmless if ignored
    })
    assert r.status_code == 200, r.text
    payload = unwrap(r.json())

    # Enveloped-new: {"points":[...], optional "anomalies":[]}
    if isinstance(payload, dict) and "anomalies" in payload:
        assert payload["anomalies"] == []
        return

    # Points-only dict: infer from is_outlier flags
    if isinstance(payload, dict) and "points" in payload:
        assert all(not p.get("is_outlier") for p in payload["points"])
        return

    # Legacy list shape
    assert isinstance(payload, list)
    assert all((isinstance(row, dict) and not row.get("is_outlier")) for row in payload)


def test_anomaly_known_source_with_no_data_returns_empty(db, reset_db):
    # Known source exists but no metric_daily rows
    db.execute(sa.text("INSERT INTO sources (id, name) VALUES (912, 'empty-demo') ON CONFLICT DO NOTHING"))
    db.commit()

    r = client.get("/api/metrics/anomaly/rolling", params={
        "source_name": "empty-demo",
        "metric": "events_total",
        "window": 3,
        "z_thresh": 3.0,
    })
    assert r.status_code == 200, r.text

    payload = unwrap(r.json())
    if isinstance(payload, dict):
        # New/points-only dict
        assert payload.get("points", []) == []
        # anomalies may be omitted; if present, must be empty
        assert payload.get("anomalies", []) in ([], None)
    else:
        # Legacy list
        assert payload == []
