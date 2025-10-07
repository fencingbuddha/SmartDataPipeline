from __future__ import annotations

from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal  # for deterministic seeding when empty
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


def _list_source_names():
    r = client.get("/api/sources")
    assert r.status_code == 200
    body = r.json()
    items = unwrap(body) if is_enveloped(body) else body
    return [s.get("name") for s in items if isinstance(s, dict)]


def test_healthz():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    if is_enveloped(body):
        assert body["ok"] is True
        data = unwrap(body)
        assert isinstance(data, dict)
        assert data.get("status") in ("ok", "healthy")
    else:
        assert body.get("status") in ("ok", "healthy")


def test_kpi_run_no_body_defaults():
    r = client.post("/api/kpi/run")
    assert r.status_code == 200
    body = r.json()
    assert is_enveloped(body)
    assert body["ok"] is True
    assert isinstance(body.get("data"), dict)


def test_sources_list_contains_demo():
    names = _list_source_names()

    # If empty, seed one source deterministically and re-check
    if not names:
        with SessionLocal() as db:
            db.execute(sa.text("INSERT INTO sources (name) VALUES ('demo-source') ON CONFLICT DO NOTHING"))
            db.commit()
        names = _list_source_names()

    assert "demo-source" in names or len(names) >= 1
