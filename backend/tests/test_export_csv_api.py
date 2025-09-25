from fastapi.testclient import TestClient
from app.main import app
import sqlalchemy as sa

client = TestClient(app)

def _seed(db):
    db.execute(sa.text("INSERT INTO sources (id, name) VALUES (301, 'demo') ON CONFLICT DO NOTHING"))
    db.execute(sa.text("""
        INSERT INTO metric_daily (metric_date, source_id, metric, value, value_count, value_sum, value_avg)
        VALUES
          ('2025-09-20', 301, 'events_total', 5, 1, 5, 5),
          ('2025-09-21', 301, 'events_total', 7, 1, 7, 7)
    """))
    db.commit()

def test_export_csv_headers_and_payload(db, reset_db):
    _seed(db)
    r = client.get("/api/metrics/export/csv", params={
        "source_name": "demo",
        "metric": "events_total",
        "start_date": "2025-09-20",
        "end_date": "2025-09-22",
    })
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type","")
    header = r.text.splitlines()[0]
    # expect the “full shape” columns to be present
    for col in ("metric_date","source_id","metric","value","value_count","value_sum","value_avg"):
        assert col in header
    assert "2025-09-20" in r.text
    assert "2025-09-21" in r.text
