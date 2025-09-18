from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.models import MetricDaily, Source

client = TestClient(app)

def _seed(db):
    s1 = Source(name="seed-src-1")
    s2 = Source(name="seed-src-2")
    db.add_all([s1, s2])
    db.flush()

    db.add_all([
        MetricDaily(metric_date=date(2025, 9, 16), source_id=s1.id, metric="events_total", value=12),
        MetricDaily(metric_date=date(2025, 9, 17), source_id=s1.id, metric="events_total", value=3),
        MetricDaily(metric_date=date(2025, 9, 17), source_id=s2.id, metric="events_total", value=9),
    ])
    db.commit()
    return s1.id, s2.id

def test_metrics_daily_filters(db, reset_db):
    s1_id, _ = _seed(db)
    r = client.get("/api/metrics/daily", params={
        "source_id": s1_id,
        "metric": "events_total",
        "start_date": "2025-09-16",
        "end_date": "2025-09-17",
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]["metric_date"] == "2025-09-16"
    assert data[1]["value"] == 3

def test_metrics_daily_empty(db, reset_db):
    r = client.get("/api/metrics/daily", params={"source_id": 999999})
    assert r.status_code == 200
    assert r.json() == []
