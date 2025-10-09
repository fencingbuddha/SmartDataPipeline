"""
Title: metrics/daily supports avg and count (UAT)
Goal: Prove different aggs are computed and returned.
"""
import io  # (kept in case you switch back to CSV later)
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.uat
client = TestClient(app)

def _unwrap_data(payload):
    # metrics/daily returns an envelope: {ok, data, error, meta}
    return payload.get("data", payload)

def test_metrics_daily_avg_and_count():
    source = "uat-source-metrics-agg"
    metric = "events_total"

    d0 = date.today()
    d1 = d0 + timedelta(days=1)

    # Ingest two JSON events on the same day -> sum=9, avg=4.5, count=2
    events = [
        {"timestamp": f"{d0.isoformat()}T00:00:00Z", "value": 4, "metric": metric, "source": source},
        {"timestamp": f"{d0.isoformat()}T01:00:00Z", "value": 5, "metric": metric, "source": source},
    ]
    r_ing = client.post("/api/ingest", params={"source_name": source}, json=events)
    assert r_ing.status_code == 200, r_ing.text

    # KPI: clean_events -> metric_daily
    r_kpi = client.post(
        "/api/kpi/run",
        params={"source_name": source, "metric": metric, "start_date": d0.isoformat(), "end_date": d1.isoformat()},
    )
    assert r_kpi.status_code in (200, 201, 202), r_kpi.text

    # AVG
    r_avg = client.get(
        "/api/metrics/daily",
        params={
            "source_name": source,
            "metric": metric,
            "start_date": d0.isoformat(),
            "end_date": d1.isoformat(),
            "agg": "avg",
        },
    )
    assert r_avg.status_code == 200, r_avg.text
    data_avg = _unwrap_data(r_avg.json())
    assert isinstance(data_avg, list) and len(data_avg) >= 1, r_avg.text
    assert abs(float(data_avg[0]["value"]) - 4.5) < 1e-6

    # COUNT
    r_cnt = client.get(
        "/api/metrics/daily",
        params={
            "source_name": source,
            "metric": metric,
            "start_date": d0.isoformat(),
            "end_date": d1.isoformat(),
            "agg": "count",
        },
    )
    assert r_cnt.status_code == 200, r_cnt.text
    data_cnt = _unwrap_data(r_cnt.json())
    assert isinstance(data_cnt, list) and len(data_cnt) >= 1, r_cnt.text
    assert int(data_cnt[0]["value"]) == 2
