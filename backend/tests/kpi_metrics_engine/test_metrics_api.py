from __future__ import annotations

from fastapi.testclient import TestClient
from app.main import app
import sqlalchemy as sa

client = TestClient(app)

# Reuse helpers if available
try:
    from _helpers import unwrap  # noqa: F401
except Exception:
    def unwrap(obj):
        if isinstance(obj, dict) and "ok" in obj and "data" in obj:
            return obj["data"]
        return obj


def _seed(db):
    # seed two sources + metric_daily rows so names are discoverable per source
    db.execute(sa.text("INSERT INTO sources (id, name) VALUES (201, 'demo') ON CONFLICT DO NOTHING"))
    db.execute(sa.text("INSERT INTO sources (id, name) VALUES (202, 'alt') ON CONFLICT DO NOTHING"))
    db.execute(sa.text("""
        INSERT INTO metric_daily (metric_date, source_id, metric, value_sum, value_avg, value_count, value_distinct)
        VALUES
          ('2025-09-20', 201, 'events_total', 5.0, 5.0, 1, NULL),
          ('2025-09-20', 201, 'errors_total',  1.0, 1.0, 1, NULL),
          ('2025-09-21', 202, 'events_total', 9.0, 9.0, 1, NULL)
        ON CONFLICT (metric_date, source_id, metric) DO UPDATE
        SET value_sum = EXCLUDED.value_sum,
            value_avg = EXCLUDED.value_avg,
            value_count = EXCLUDED.value_count,
            value_distinct = EXCLUDED.value_distinct
    """))
    db.commit()


def test_metric_names_scoped_by_source(db, reset_db):
    _seed(db)

    r1 = client.get("/api/metrics/names", params={"source_name": "demo"})
    assert r1.status_code == 200, r1.text
    names1 = set(unwrap(r1.json()))
    assert {"events_total", "errors_total"} <= names1

    r2 = client.get("/api/metrics/names", params={"source_name": "alt"})
    assert r2.status_code == 200, r2.text
    names2 = set(unwrap(r2.json()))
    assert names2 == {"events_total"}

    # unknown source -> current API returns 404 (enveloped); allow 200+[] if policy changes later
    r3 = client.get("/api/metrics/names", params={"source_name": "nope"})
    assert r3.status_code in (200, 404)
    if r3.status_code == 200:
        assert unwrap(r3.json()) == []
    else:
        body = r3.json()
        # accept either enveloped error or FastAPI default {"detail": "..."}
        if isinstance(body, dict) and "ok" in body and "data" in body:
            assert body["ok"] is False
            assert isinstance(body.get("error"), dict)
        else:
            assert "detail" in body
