from datetime import date
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import date, timedelta

SOURCE = "uat-demo-source"
METRIC = "events_total"

def _get_source_id(session: Session, source_name: str) -> int:
    row = session.execute(
        text("SELECT id FROM sources WHERE name = :n"), {"n": source_name}
    ).fetchone()
    assert row, f"Source '{source_name}' not found (did ingest run?)"
    return int(row[0])

def _count_forecasts(session: Session, sid: int, metric: str) -> int:
    return session.execute(
        text("SELECT COUNT(*) FROM forecast_results WHERE source_id=:s AND metric=:m"),
        {"s": sid, "m": metric},
    ).scalar_one()

@pytest.mark.order(1000)
def test_forecast_end_to_end_idempotent_target_date(client, db: Session):
    today = date.today().isoformat()

    # 1) Ingest two events directly (JSON array)
    events = [
        {"timestamp": today, "value": 4, "metric": METRIC, "source": SOURCE},
        {"timestamp": today, "value": 5, "metric": METRIC, "source": SOURCE},
    ]
    r_ing = client.post("/api/ingest", json=events)
    assert r_ing.status_code in (200, 201), r_ing.text

    # 2) KPI daily (JSON body)
    r_kpi = client.post("/api/kpi/run", json={"source_name": SOURCE, "metric": METRIC})
    assert r_kpi.status_code in (200, 201), r_kpi.text

    # 3) Forecast run (QUERY PARAMS)
    r_fc = client.post("/api/forecast/run", params={"source_name": SOURCE, "metric": METRIC, "horizon": 7})
    assert r_fc.status_code in (200, 201, 202), r_fc.text
    body = r_fc.json()
    assert isinstance(body, dict), body
    assert "inserted" in body and body["inserted"] >= 7, body

    # 4) Verify ≥7 rows exist
    sid = _get_source_id(db, SOURCE)
    before = _count_forecasts(db, sid, METRIC)
    assert before >= 7, f"Expected at least 7 forecast rows; got {before}"

    # 5) Re-run → idempotent
    r_fc2 = client.post("/api/forecast/run", params={"source_name": SOURCE, "metric": METRIC, "horizon": 7})
    assert r_fc2.status_code in (200, 201, 202), r_fc2.text
    body2 = r_fc2.json()
    assert isinstance(body2, dict), body2

    after = _count_forecasts(db, sid, METRIC)
    assert after == before, f"Idempotency failed: before={before}, after={after}"

    # 6) GET daily (params) – requires start_date & end_date
    start = date.today()
    end = start + timedelta(days=14)   # safely covers the 7-day horizon
    r_get = client.get(
        "/api/forecast/daily",
        params={
            "source_name": SOURCE,
            "metric": METRIC,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    assert r_get.status_code == 200, r_get.text
    payload = r_get.json()
    items = payload if isinstance(payload, list) else payload.get("items") or payload.get("data") or []
    assert len(items) >= 7, f"Expected >=7 items; got {len(items)}"
    assert {"date", "yhat"} <= set(items[0].keys()), f"Unexpected item keys: {items[0].keys()}"
