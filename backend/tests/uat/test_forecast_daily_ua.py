"""
Title: Forecast daily returns rows (UAT)
User Story: After running a forecast, I can retrieve daily predictions.
"""
import io, time
from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.db.session import SessionLocal

pytestmark = pytest.mark.uat
client = TestClient(app)

def _ensure_source(name: str) -> None:
    db = SessionLocal()
    try:
        db.execute(
            text("INSERT INTO sources(name) VALUES (:n) ON CONFLICT (name) DO NOTHING"),
            {"n": name},
        )
        db.commit()
    finally:
        db.close()

def test_forecast_daily_returns_rows():
    source = "uat-source-forecast-daily"
    metric = "events_total"

    # Make sure the Source exists (run_forecast() requires it)
    _ensure_source(source)

    # Seed ~30 days of history via /api/upload so forecasting has training data
    start = date.today() - timedelta(days=30)
    rows = ["timestamp,value,metric,source"]
    for i in range(30):
        d = start + timedelta(days=i)
        rows.append(f"{d.isoformat()},{100+i},{metric},{source}")
    csv_bytes = ("\n".join(rows)).encode()
    files = {"file": ("history.csv", io.BytesIO(csv_bytes), "text/csv")}
    r = client.post("/api/upload", params={"source_name": source}, files=files)
    assert r.status_code in (200, 201), r.text

    # Aggregate history into metric_daily so the forecast has a training series
    r_kpi = client.post(
        "/api/kpi/run",
        params={
            "source_name": source,
            "metric": metric,
            "start_date": start.isoformat(),
            "end_date": date.today().isoformat(),
        },
    )
    assert r_kpi.status_code in (200, 201, 202), r_kpi.text

    # Run forecast for the next 2 days
    r = client.post(
        "/api/forecast/run",
        params={"source_name": source, "metric": metric, "horizon_days": 2},
    )
    assert r.status_code in (200, 202), r.text

    # Pull the forecasted window (tomorrow -> +2 days)
    d0 = date.today() + timedelta(days=1)
    d1 = d0 + timedelta(days=2)

    # small poll in case writes are async/batched
    deadline = time.time() + 3.0
    last = None
    data = None
    while time.time() < deadline:
        resp = client.get(
            "/api/forecast/daily",
            params={
                "source_name": source,
                "metric": metric,
                "start_date": d0.isoformat(),
                "end_date": d1.isoformat(),
            },
        )
        last = resp
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) >= 1:
                break
        time.sleep(0.1)

    assert last is not None and last.status_code == 200, (last and last.text)
    assert isinstance(data, list) and len(data) >= 1, f"no rows returned; last={last.text}"
    # sanity: expected keys
    assert {"date", "metric", "yhat"} <= set(data[0].keys())
