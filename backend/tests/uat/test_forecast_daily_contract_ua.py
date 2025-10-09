"""
Title: Forecast daily returns rows (UAT)
User Story: As a user, I can fetch forecasted daily values after running a forecast.
Created: 2025-10-08
Last Updated: 2025-10-08
"""
import io
import time
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.db.session import SessionLocal

pytestmark = pytest.mark.uat
client = TestClient(app)

SOURCE = "uat-source"
METRIC = "events_total"


def ensure_source() -> None:
    db = SessionLocal()
    try:
        db.execute(
            text("INSERT INTO sources(name) VALUES (:n) ON CONFLICT (name) DO NOTHING"),
            {"n": SOURCE},
        )
        db.commit()
    finally:
        db.close()


def upload_history(days: int = 30) -> None:
    """Seed simple daily history via /api/upload + run KPI so training data exists."""
    start = date.today() - timedelta(days=days)
    rows = ["timestamp,value,metric,source"]
    for i in range(days):
        d = start + timedelta(days=i)
        rows.append(f"{d.isoformat()},{100+i},{METRIC},{SOURCE}")
    csv_bytes = ("\n".join(rows)).encode()

    files = {"file": ("history.csv", io.BytesIO(csv_bytes), "text/csv")}
    r = client.post("/api/upload", params={"source_name": SOURCE}, files=files)
    assert r.status_code in (200, 201), r.text

    r = client.post("/api/kpi/run", params={"source_name": SOURCE, "metric": METRIC})
    assert r.status_code in (200, 201, 202), r.text


def test_forecast_daily_returns_rows():
    ensure_source()
    upload_history(days=30)

    r = client.post(
        "/api/forecast/run",
        params={"source_name": SOURCE, "metric": METRIC, "horizon_days": 3},
    )
    assert r.status_code in (200, 202), r.text

    start_future = (date.today() + timedelta(days=1)).isoformat()
    end_future = (date.today() + timedelta(days=4)).isoformat()
    r = client.get(
        "/api/forecast/daily",
        params={
            "source_name": SOURCE,
            "metric": METRIC,
            "start_date": start_future,
            "end_date": end_future,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list), f"Unexpected payload: {data!r}"
    if not data:
        deadline = time.time() + 2.0
        last = []
        while time.time() < deadline and not last:
            rr = client.get(
                "/api/forecast/daily",
                params={
                    "source_name": SOURCE,
                    "metric": METRIC,
                    "start_date": start_future,
                    "end_date": end_future,
                },
            )
            last = rr.json() if rr.status_code == 200 else []
            time.sleep(0.1)
        data = last

    assert len(data) >= 1, f"No forecast rows returned. Response: {data!r}"
    for row in data:
        assert {"date", "metric", "yhat"}.issubset(row.keys())
        assert row["metric"] == METRIC
