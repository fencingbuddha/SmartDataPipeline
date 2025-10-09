"""
Title: Metrics names and CSV export are discoverable and downloadable (UAT)
User Story: After ingesting events for a source, I can list available metric names and export daily metrics to CSV.
"""
import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from app.main import app

pytestmark = pytest.mark.uat
client = TestClient(app)

SOURCE = "uat-metrics-names"
M1 = "events_total"
M2 = "clicks_total"


def _unwrap_data(payload):
    if isinstance(payload, dict) and "ok" in payload and "data" in payload:
        return payload["data"]
    return payload


def test_metrics_names_and_export_csv_roundtrip():
    d0 = date.today()
    d1 = d0 + timedelta(days=1)

    # Seed two metrics so /api/metrics/names has something to report
    events = [
        {"timestamp": d0.isoformat(), "value": 1, "metric": M1, "source": SOURCE},
        {"timestamp": d0.isoformat(), "value": 3, "metric": M2, "source": SOURCE},
    ]
    r_ing = client.post(
        "/api/ingest",
        params={"source_name": SOURCE},
        content=json.dumps(events),
        headers={"Content-Type": "application/json"},
    )
    assert r_ing.status_code in (200, 201), r_ing.text

    # Names endpoint: should include both metrics for this source
    r_names = client.get("/api/metrics/names", params={"source_name": SOURCE})
    assert r_names.status_code == 200, r_names.text
    names = _unwrap_data(r_names.json())
    assert isinstance(names, list)
    assert M1 in names and M2 in names

    # Export CSV: should return text/csv and contain header + at least one row
    r_csv = client.get(
        "/api/metrics/export/csv",
        params={
            "source_name": SOURCE,
            "metric": M1,
            "start_date": d0.isoformat(),
            "end_date": d1.isoformat(),
        },
    )
    assert r_csv.status_code == 200, r_csv.text
    ctype = r_csv.headers.get("content-type", "")
    assert "text/csv" in ctype or "application/csv" in ctype.lower()
    body = r_csv.text
    assert "metric_date" in body or "date" in body  # header
    assert SOURCE in body or M1 in body             # some row content
