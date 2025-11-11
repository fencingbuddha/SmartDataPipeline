"""
Title: Upload empty CSV yields staging but no KPI rows (UAT)
User Story: As a user, I get a successful staging response for an empty CSV, but there are no metrics afterward.
Created: 2025-10-08
Last Updated: 2025-10-08
"""
from io import BytesIO
from datetime import date, timedelta
import pytest

pytestmark = pytest.mark.uat


def _unwrap_data(payload):
    if isinstance(payload, dict) and "data" in payload and "ok" in payload:
        return payload["data"]
    return payload


def test_upload_empty_csv_yields_no_metrics(client):
    source = "uat-source"
    metric = "events_total"
    d0 = date.today()
    d1 = d0 + timedelta(days=1)

    # Header-only CSV (no data rows) — server returns 200 with staging info
    csv = b"timestamp,value,metric,source\n"
    files = {"file": ("empty.csv", BytesIO(csv), "text/csv")}
    r = client.post("/api/upload", params={"source_name": source}, files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    data = _unwrap_data(body)
    assert isinstance(data, dict) and "staging_id" in data, body

    # Running KPI over today->tomorrow should produce no metric_daily rows
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
    daily = _unwrap_data(r.json())
    assert isinstance(daily, list) and len(daily) == 0
