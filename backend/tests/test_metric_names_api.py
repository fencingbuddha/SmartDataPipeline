from fastapi.testclient import TestClient
from app.main import app
import sqlalchemy as sa

client = TestClient(app)

def _seed(db):
    # seed two sources + metric_daily rows so names are discoverable per source
    db.execute(sa.text("INSERT INTO sources (id, name) VALUES (201, 'demo'), (202, 'alt') ON CONFLICT DO NOTHING"))
    db.execute(sa.text("""
        INSERT INTO metric_daily (metric_date, source_id, metric, value)
        VALUES
          ('2025-09-20', 201, 'events_total', 5),
          ('2025-09-20', 201, 'errors_total',  1),
          ('2025-09-21', 202, 'events_total', 9)
    """))
    db.commit()

def test_metric_names_scoped_by_source(db, reset_db):
    _seed(db)
    r1 = client.get("/api/metrics/names", params={"source_name":"demo"})
    assert r1.status_code == 200
    names1 = set(r1.json())
    assert {"events_total", "errors_total"} <= names1

    r2 = client.get("/api/metrics/names", params={"source_name":"alt"})
    assert r2.status_code == 200
    names2 = set(r2.json())
    assert names2 == {"events_total"}

    # unknown source -> empty list (or 404 if your API chooses that)
    r3 = client.get("/api/metrics/names", params={"source_name":"nope"})
    assert r3.status_code in (200, 404)
    if r3.status_code == 200:
        assert r3.json() == []
