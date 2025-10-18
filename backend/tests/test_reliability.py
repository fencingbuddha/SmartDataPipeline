# tests/test_reliability.py
from datetime import date, timedelta
from io import BytesIO

from app.db.session import SessionLocal
from app.models.source import Source

SOURCE = "demo-source"
METRIC = "events_total"

def _ensure_source():
    """Create the Source row if missing (idempotent)."""
    with SessionLocal() as db:
        obj = db.query(Source).filter_by(name=SOURCE).first()
        if obj is None:
            db.add(Source(name=SOURCE))
            db.commit()

def _upload_minimal(client):
    """Seed a few rows so forecast has something to model."""
    today = date.today()
    rows = [
        "timestamp,value,metric,source",
        f"{today.isoformat()},4,{METRIC},{SOURCE}",
        f"{today.isoformat()},5,{METRIC},{SOURCE}",
        f"{(today - timedelta(days=1)).isoformat()},7,{METRIC},{SOURCE}",
    ]
    files = {"file": ("data.csv", BytesIO("\n".join(rows).encode()), "text/csv")}
    client.post("/api/upload", params={"source_name": SOURCE}, files=files)

    # Try ingest/KPI if present (don’t fail test if not)
    try:
        client.post("/api/ingest", params={"source_name": SOURCE})
    except Exception:
        pass
    try:
        client.post("/api/kpi/run", params={"source_name": SOURCE, "metric": METRIC})
    except Exception:
        pass

def test_forecast_upsert_is_idempotent(client):
    _ensure_source()
    _upload_minimal(client)

    q = {"source_name": SOURCE, "metric": METRIC}

    r1 = client.post("/api/forecast/run", params=q)
    assert r1.status_code in (200, 201), f"First run failed: {r1.status_code} {r1.text}"

    r2 = client.post("/api/forecast/run", params=q)
    assert r2.status_code in (200, 201), f"Second run failed: {r2.status_code} {r2.text}"

    # ADD THESE LINES ↓↓↓
    today = date.today()
    start = today.isoformat()
    end = (today + timedelta(days=14)).isoformat()

    d = client.get("/api/forecast/daily", params={**q, "start_date": start, "end_date": end})
    assert d.status_code == 200, d.text
    body = d.json() or []
    dates = [row.get("target_date") or row.get("date") for row in body]
    assert len(dates) == len(set(dates)), f"Duplicate forecast rows found: {dates}"