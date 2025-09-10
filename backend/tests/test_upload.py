import io, json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_csv_upload_ok(tmp_path):
    csv_content = "id,name\n1,Alice\n2,Bob\n"
    files = {"file": ("sample.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    r = client.post("/api/upload?source_name=test-source", files=files)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["records_ingested"] == 2
    assert body["filename"] == "sample.csv"


def test_json_upload_ok():
    json_data = json.dumps([{"a": 1}, {"a": 2}])
    files = {"file": ("data.json", io.BytesIO(json_data.encode("utf-8")), "application/json")}
    r = client.post("/api/upload?source_name=json-source", files=files)
    assert r.status_code == 201
    body = r.json()
    assert body["records_ingested"] == 2


def test_reject_bad_type():
    files = {"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")}
    r = client.post("/api/upload?source_name=bad", files=files)
    assert r.status_code == 400
    assert "Only CSV/JSON" in r.json()["detail"]
