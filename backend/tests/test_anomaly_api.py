from fastapi.testclient import TestClient
from app.main import app
import sqlalchemy as sa

client = TestClient(app)

def _seed_series_with_spike(db):
    db.execute(sa.text("INSERT INTO sources (id, name) VALUES (401, 'demo') ON CONFLICT DO NOTHING"))
    # mostly 10s, one big spike 100 on 2025-09-06
    rows = [
        ("2025-09-01", 10), ("2025-09-02", 11), ("2025-09-03",  9),
        ("2025-09-04", 10), ("2025-09-05", 10), ("2025-09-06", 100),
        ("2025-09-07", 10),
    ]
    for d, v in rows:
        db.execute(sa.text("""
            INSERT INTO metric_daily (metric_date, source_id, metric, value, value_count, value_sum, value_avg)
            VALUES (:d, 401, 'events_total', :v, 1, :v, :v)
        """), {"d": d, "v": v})
    db.commit()

def test_anomaly_rolling_flags_spike(db, reset_db):
    _seed_series_with_spike(db)
    r = client.get("/api/metrics/anomaly/rolling", params={
        "source_name":"demo", "metric":"events_total",
        "start_date":"2025-09-01", "end_date":"2025-09-08", "window":3
    })
    assert r.status_code == 200
    out = r.json()
    assert isinstance(out, list) and len(out) >= 7
    # at least one row flagged
    assert any(row.get("is_outlier") for row in out)
