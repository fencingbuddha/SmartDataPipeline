"""
Title: Run forecast -> results persisted (UAT)
User Story: As a user, I can generate a forecast so I can view predictions.
Created: 2025-10-07
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
from app.models.forecast_results import ForecastResults as ForecastResultModel

pytestmark = pytest.mark.uat
client = TestClient(app)

SOURCE = "uat-source"
METRIC = "events_total"


def ensure_source() -> None:
    """Insert the source if it doesn't exist."""
    db = SessionLocal()
    try:
        db.execute(
            text("INSERT INTO sources(name) VALUES (:n) ON CONFLICT (name) DO NOTHING"),
            {"n": SOURCE},
        )
        db.commit()
    finally:
        db.close()


def upload_history_and_compute_kpis(days: int = 60) -> None:
    """
    Seed N days of daily data via the public upload endpoint,
    then run KPI aggregation so MetricDaily has training data.
    """
    start = date.today() - timedelta(days=days)
    rows = ["timestamp,value,metric,source"]
    for i in range(days):
        d = start + timedelta(days=i)
        rows.append(f"{d.isoformat()},{100+i},{METRIC},{SOURCE}")
    csv_bytes = ("\n".join(rows)).encode()

    files = {"file": ("history.csv", io.BytesIO(csv_bytes), "text/csv")}
    r = client.post("/api/upload", params={"source_name": SOURCE}, files=files)
    assert r.status_code in (200, 201), f"Upload failed: {r.status_code} {r.text}"

    r_kpi = client.post("/api/kpi/run", params={"source_name": SOURCE, "metric": METRIC})
    assert r_kpi.status_code in (200, 201, 202), f"KPI run failed: {r_kpi.status_code} {r_kpi.text}"


def test_forecast_persists_results():
    ensure_source()
    upload_history_and_compute_kpis(days=60)

    resp = client.post(
        "/api/forecast/run",
        params={"source_name": SOURCE, "metric": METRIC, "horizon_days": 3},
    )
    if resp.status_code not in (200, 202):
        print("DEBUG forecast/run status:", resp.status_code)
        print("DEBUG forecast/run body:", resp.text)
    assert resp.status_code in (200, 202)

    db = SessionLocal()
    try:
        future_start = date.today() + timedelta(days=1)
        found = 0
        deadline = time.time() + 2.0
        while time.time() < deadline:
            rows = (
                db.query(ForecastResultModel)
                .filter(ForecastResultModel.metric == METRIC)
                .filter(ForecastResultModel.target_date >= future_start)
                .all()
            )
            found = len(rows)
            if found >= 1:
                break
            time.sleep(0.1)

        assert found >= 1, "No forecast rows found in forecast_results"
    finally:
        db.close()
