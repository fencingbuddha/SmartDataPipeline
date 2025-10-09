# tests/uat/test_metrics_daily_by_source_id_ua.py
from datetime import date, datetime, timedelta
import json
import time
from typing import Any, Dict, List, Optional

# Relies on the project's TestClient "client" fixture from conftest.py
# Ingests JSON directly (NOT multipart) because /api/ingest expects JSON.
# Seeds two events with different timestamps on the SAME day to avoid any
# (source, metric, timestamp) upsert/unique-key collapsing.
# Then runs KPIs and queries /api/metrics/daily by source_id with agg=count.

SOURCE = "uat-source"
METRIC = "events_total"


def _unwrap_data(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    return payload.get("data") or []


def _find_source_id(client, source_name: str) -> Optional[int]:
    r = client.get("/api/sources")
    assert r.status_code == 200, r.text
    data = _unwrap_data(r.json())
    for row in data:
        if str(row.get("name")) == source_name:
            return row.get("id")
    return None


def _row_date_str(row: Dict[str, Any]) -> Optional[str]:
    # API may return 'metric_date' or 'date'
    return row.get("metric_date") or row.get("date")


def _value_from_row(row: Dict[str, Any]) -> Optional[float]:
    # If agg=count was used, many implementations return 'value'
    if "value" in row:
        return row["value"]
    # Otherwise the full shape may include value_count
    if "value_count" in row:
        return row["value_count"]
    return None


def _seed_via_ingest_json_then_kpi(client, events: List[Dict[str, Any]], d0: date, d1: date) -> None:
    r_ing = client.post(
        "/api/ingest",
        params={"source_name": SOURCE},
        content=json.dumps(events),
        headers={"Content-Type": "application/json"},
    )
    assert r_ing.status_code in (200, 201), r_ing.text

    r_kpi = client.post(
        "/api/kpi/run",
        params={
            "source_name": SOURCE,
            "metric": METRIC,
            "start_date": d0.isoformat(),
            "end_date": d1.isoformat(),
        },
    )
    assert r_kpi.status_code in (200, 201, 202), r_kpi.text


def test_metrics_daily_by_source_id_and_count(client):
    d0 = date.today()
    d1 = d0 + timedelta(days=1)

    # Use two DISTINCT timestamps within the same day to avoid dedupe/upsert collapse.
    t0 = datetime.combine(d0, datetime.min.time()).replace(hour=0, minute=0, second=0, microsecond=0)
    t1 = t0.replace(minute=1)  # still same day, different timestamp

    # Two events on the same day => count=2 (sum=9, avg=4.5) once both are retained
    events = [
        {"timestamp": t0.isoformat(), "value": 4, "metric": METRIC, "source": SOURCE},
        {"timestamp": t1.isoformat(), "value": 5, "metric": METRIC, "source": SOURCE},
    ]

    _seed_via_ingest_json_then_kpi(client, events, d0, d1)

    # Resolve source_id via API (exercise the source_id code path)
    src_id = _find_source_id(client, SOURCE)
    assert src_id is not None, "Source row not found"

    params = {
        "source_id": src_id,
        "metric": METRIC,
        "start_date": d0.isoformat(),
        "end_date": d1.isoformat(),
        "agg": "count",
        "limit": 1000,  # harmless if ignored
    }

    # Brief poll in case KPI writes are batched/async
    deadline = time.time() + 2.0
    last = None
    data_cnt: List[Dict[str, Any]] = []
    while time.time() < deadline:
        last = client.get("/api/metrics/daily", params=params)
        assert last.status_code == 200, last.text
        data_cnt = _unwrap_data(last.json())
        if isinstance(data_cnt, list) and len(data_cnt) >= 1:
            break
        time.sleep(0.1)

    assert isinstance(data_cnt, list) and len(data_cnt) >= 1, f"empty response: {(last and last.text)}"

    # Find the row for the day d0 (API may call the date field 'metric_date' or 'date')
    row_for_d0 = next((r for r in data_cnt if _row_date_str(r) == d0.isoformat()), data_cnt[0])
    observed = _value_from_row(row_for_d0)

    # Expect 2 because we inserted two distinct timestamps on the same day.
    assert observed == 2, f"expected count=2 for {d0.isoformat()}, got {observed} (row={row_for_d0})"


def test_metrics_daily_by_unknown_source_id_returns_empty(client):
    d0 = date.today()
    d1 = d0 + timedelta(days=1)

    params = {
        "source_id": 999_999_999,  # unlikely to exist
        "metric": METRIC,
        "start_date": d0.isoformat(),
        "end_date": d1.isoformat(),
        "agg": "count",
    }
    r = client.get("/api/metrics/daily", params=params)
    assert r.status_code == 200, r.text
    data = _unwrap_data(r.json())
    assert isinstance(data, list) and len(data) == 0, f"expected empty data for unknown source_id, got: {data}"
