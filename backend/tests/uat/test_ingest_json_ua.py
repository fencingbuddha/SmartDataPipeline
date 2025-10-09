"""
Title: Ingest JSON -> metrics available (UAT)
User Story: As a user, I can POST JSON events and see daily metrics.
Created: 2025-10-08
Last Updated: 2025-10-08
"""
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.uat
client = TestClient(app)


def _unwrap_data(payload):
    if isinstance(payload, dict) and "data" in payload and "ok" in payload:
        return payload["data"]
    return payload


def test_ingest_json_then_metrics_visible():
    source = "uat-source"
    metric = "events_total"
    d0 = date.today()
    d1 = d0 + timedelta(days=1)

    events = [
        {"timestamp": f"{d0.isoformat()}T00:00:00Z", "value": 5, "metric": metric, "source": source},
        {"timestamp": f"{d0.isoformat()}T12:00:00Z", "value": 2, "metric": metric, "source": source},
    ]

    r = client.post("/api/ingest", params={"source_name": source}, json=events)
    assert r.status_code == 200, r.text

    r = client.post(
        "/api/kpi/run",
        params={"source_name": source, "metric": metric, "start_date": d0.isoformat(), "end_date": d1.isoformat()},
    )
    assert r.status_code in (200, 201, 202), r.text

    r = client.get(
        "/api/metrics/daily",
        params={"source_name": source, "metric": metric, "start_date": d0.isoformat(), "end_date": d1.isoformat()},
    )
    assert r.status_code == 200, r.text
    data = _unwrap_data(r.json())
    assert isinstance(data, list) and len(data) >= 1, data
