from datetime import datetime, timedelta, UTC
from fastapi.testclient import TestClient
import sqlalchemy as sa
from app.main import app
from app.db.session import SessionLocal
from app.models.source import Source
from app.models.clean_event import CleanEvent
from app.models.metric_daily import MetricDaily

client = TestClient(app)

def _reset(db):
    db.execute(sa.text("DELETE FROM metric_daily"))
    db.execute(sa.text("DELETE FROM clean_events"))
    db.commit()

def _ensure_source(db, sid=1):
    src = db.get(Source, sid)
    if not src:
        db.add(Source(id=sid, name="demo"))
        db.commit()

def test_kpi_happy_path():
    db = SessionLocal()
    try:
        _reset(db)
        _ensure_source(db, 1)

        base = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        rows = [
            CleanEvent(ts=base - timedelta(days=1, hours=1), source_id=1, metric="orders", value=10),
            CleanEvent(ts=base - timedelta(days=1, hours=2), source_id=1, metric="orders", value=20),
            CleanEvent(ts=base - timedelta(days=1, hours=3), source_id=1, metric="orders", value=30),
            CleanEvent(ts=base,                          source_id=1, metric="orders", value=40),
        ]
        db.add_all(rows)
        db.commit()

        resp = client.post("/api/kpi/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["rows_upserted"] >= 2  # yesterday + today

        res = db.execute(sa.select(MetricDaily)).scalars().all()
        # find yesterday
        yesterday = (base - timedelta(days=1)).date()
        md = next(r for r in res if r.metric_date == yesterday and r.metric == "orders")
        assert float(md.value_sum) == 60.0
        assert round(float(md.value_avg), 2) == 20.00
        assert md.value_count == 3
    finally:
        db.close()

def test_kpi_empty_ok():
    db = SessionLocal()
    try:
        _reset(db)
        resp = client.post("/api/kpi/run")
        assert resp.status_code == 200
        assert resp.json()["rows_upserted"] == 0
    finally:
        db.close()
