from __future__ import annotations

from fastapi.testclient import TestClient
from app.main import app
import sqlalchemy as sa

client = TestClient(app)

# Reuse helpers if present
try:
    from _helpers import unwrap, is_enveloped  # noqa: F401
except Exception:
    def is_enveloped(obj):
        return isinstance(obj, dict) and "ok" in obj and "data" in obj
    def unwrap(obj):
        return obj["data"] if is_enveloped(obj) else obj


def test_sources_empty(reset_db):
    r = client.get("/api/sources")
    assert r.status_code == 200
    body = r.json()
    data = unwrap(body)
    assert isinstance(data, list)
    assert data == []


def test_sources_non_empty(db, reset_db):
    db.execute(sa.text("INSERT INTO sources (name) VALUES ('demo'),('alt')"))
    db.commit()

    r = client.get("/api/sources")
    assert r.status_code == 200
    body = r.json()
    items = unwrap(body)
    assert isinstance(items, list)

    names = {s.get("name") for s in items if isinstance(s, dict)}
    assert {"demo", "alt"} <= names
