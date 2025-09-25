import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_ingest_accepts_raw_json_body(reset_db):
    payload = [
        {"timestamp":"2025-09-20T00:00:00Z","value":5,"source":"demo","metric":"events_total"},
        {"timestamp":"2025-09-21T00:00:00Z","value":7,"source":"demo","metric":"events_total"},
    ]
    r = client.post("/api/ingest?source_name=demo",
                    content=json.dumps(payload),
                    headers={"Content-Type":"application/json"})
    assert r.status_code in (200, 201), r.text

def test_ingest_rejects_wrong_multipart_when_raw_expected(reset_db):
    # Only add this if your /api/ingest explicitly expects raw JSON/CSV (not multipart)
    files = {"file": ("data.json", b"[{\"a\":1}]", "application/json")}
    r = client.post("/api/ingest?source_name=demo", files=files)
    assert r.status_code in (400,415)
