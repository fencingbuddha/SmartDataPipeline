from datetime import date, timedelta
from app.models.source import Source
from app.models.metric_daily import MetricDaily

def _seed(db, *, source_name="demo-source", metric="events_total", days=120, base=50.0):
    src = Source(name=source_name)
    db.add(src); db.commit(); db.refresh(src)
    start = date.today() - timedelta(days=days)
    for i in range(days):
        db.add(MetricDaily(
            source_id=src.id,
            metric=metric,
            metric_date=start + timedelta(days=i),
            value_sum=base + 0.5 * i,
        ))
    db.commit()
    return src

def test_forecast_health_endpoint_shape_and_idempotency(client, db_session):
    src = _seed(db_session)
    r = client.get("/api/forecast/health", params={"source_name": src.name, "metric": "events_total", "window": 90})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {"trained_at", "window", "mape"}
    assert body["window"] == 90
    assert isinstance(body["mape"], (int, float))

    # Call again: should still 200 and not duplicate keys (upsert path)
    r2 = client.get("/api/forecast/health", params={"source_name": src.name, "metric": "events_total", "window": 90})
    assert r2.status_code == 200

def test_forecast_health_unknown_source(client):
    r = client.get("/api/forecast/health", params={"source_name": "nope", "metric": "events_total", "window": 90})
    assert r.status_code == 422
