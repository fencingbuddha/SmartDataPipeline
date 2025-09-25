from fastapi.testclient import TestClient
from app.main import app
import sqlalchemy as sa

client = TestClient(app)

def test_sources_empty(reset_db):
    r = client.get("/api/sources")
    assert r.status_code == 200
    assert r.json() == []

def test_sources_non_empty(db, reset_db):
    db.execute(sa.text("INSERT INTO sources (name) VALUES ('demo'),('alt')"))
    db.commit()
    r = client.get("/api/sources")
    assert r.status_code == 200
    names = {s["name"] for s in r.json()}
    assert {"demo","alt"} <= names
