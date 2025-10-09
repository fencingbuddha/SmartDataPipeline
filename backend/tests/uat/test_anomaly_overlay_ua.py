import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.db.session import SessionLocal

pytestmark = pytest.mark.uat
client = TestClient(app)

def ensure_source(name: str = "uat-source"):
    db = SessionLocal()
    db.execute(
        text("INSERT INTO sources(name) VALUES (:n) ON CONFLICT (name) DO NOTHING"),
        {"n": name},
    )
    db.commit()
    db.close()

def test_anomaly_overlay_contract():
    ensure_source("uat-source")

    r = client.get("/api/metrics/anomaly/iforest", params={
        "source_name":"uat-source",
        "metric":"events_total",
        "start_date":"2025-01-01",
        "end_date":"2025-01-10",
    })
    if r.status_code not in (200, 204):
        print("DEBUG status:", r.status_code)
        print("DEBUG body:", r.text)
    assert r.status_code in (200, 204)
