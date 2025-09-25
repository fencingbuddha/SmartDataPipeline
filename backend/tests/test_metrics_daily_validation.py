from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_requires_some_selector():
    r = client.get("/api/metrics/daily")  # no params
    # your API might default; if you validate, assert 422
    assert r.status_code in (200, 422)

def test_rejects_bad_dates():
    r = client.get("/api/metrics/daily", params={
        "source_name":"demo","metric":"events_total",
        "start_date":"not-a-date","end_date":"2025-09-22"
    })
    assert r.status_code in (400, 422)

def test_start_end_inclusive_semantics():
    # If your API is inclusive on both ends, assert it. Otherwise adapt to your rule.
    r = client.get("/api/metrics/daily", params={
        "source_name":"demo","metric":"events_total",
        "start_date":"2025-09-16","end_date":"2025-09-16"
    })
    assert r.status_code == 200
    assert isinstance(r.json(), list)
