import io, json
from fastapi.testclient import TestClient
import pandas as pd
from app.main import app
from app.db import SessionLocal
from app.models import CleanEvent

client = TestClient(app)

def _csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode()

def _json_bytes(records) -> bytes:
    return json.dumps(records).encode()

def test_ingest_csv_success(client):
    csv = b"timestamp,metric,value\n2025-09-01,sales,100\n2025-09-02,sales,200\n"
    files = {"file": ("sample.csv", io.BytesIO(csv), "text/csv")}
    r = client.post("/api/ingest?source_name=demo", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "demo"
    assert body["raw_events_inserted"] == 2
    assert body["clean_events_inserted"] == 2

def test_ingest_json_success(client):
    payload = [
        {"timestamp": "2025-09-01", "metric": "clicks", "value": 10},
        {"timestamp": "2025-09-02", "metric": "clicks", "value": 12.5},
    ]
    r = client.post(
        "/api/ingest?source_name=tjson",
        content=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["raw_events_inserted"] == 2
    assert body["clean_events_inserted"] == 2

def test_ingest_empty_file(client):
    files = {"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
    r = client.post("/api/ingest?source_name=empty", files=files)
    assert r.status_code == 400
    assert "Empty file" in r.text

def test_ingest_missing_value_column(client):
    bad = b"timestamp,metric\n2025-09-01,sales\n"
    files = {"file": ("bad.csv", io.BytesIO(bad), "text/csv")}
    r = client.post("/api/ingest?source_name=bad", files=files)
    assert r.status_code == 400
    assert "Missing numeric value column" in r.text

def test_ingest_missing_timestamp_column(client):
    bad = b"metric,value\nsales,10\n"
    files = {"file": ("bad.csv", io.BytesIO(bad), "text/csv")}
    r = client.post("/api/ingest?source_name=bad2", files=files)
    assert r.status_code == 400
    assert "Missing timestamp" in r.text or "Missing timestamp/time/date column" in r.text

    # ------------------ Happy paths ------------------

def test_ingest_csv_success(reset_db):
    df = pd.DataFrame([
        {"timestamp": "2024-01-01T00:00:00Z", "value": 10, "source": "demo"},
        {"timestamp": "2024-01-01T00:05:00Z", "value": 12, "source": "demo"},
    ])
    files = {"file": ("data.csv", io.BytesIO(_csv_bytes(df)), "text/csv")}
    r = client.post("/api/ingest?source_name=demo", files=files)
    assert r.status_code == 200
    payload = r.json()
    assert payload["inserted"] == 2

    with SessionLocal() as s:
        assert s.query(CleanEvent).count() == 2

def test_ingest_json_success(reset_db):
    records = [
        {"timestamp": "2024-01-02T00:00:00Z", "value": 5, "source": "demo"},
        {"timestamp": "2024-01-02T00:05:00Z", "value": 7, "source": "demo"},
    ]
    r = client.post("/api/ingest?source_name=demo", json=records)
    assert r.status_code == 200
    assert r.json()["inserted"] == 2

    # ------------------ Duplicates / idempotency ------------------

def test_ingest_duplicate_records_ignored(reset_db):
    df = pd.DataFrame([
        {"timestamp": "2024-01-03T00:00:00Z", "value": 1, "source": "demo"},
        {"timestamp": "2024-01-03T00:01:00Z", "value": 2, "source": "demo"},
    ])
    files = {"file": ("data.csv", io.BytesIO(_csv_bytes(df)), "text/csv")}
    r1 = client.post("/api/ingest?source_name=demo", files=files)
    assert r1.status_code == 200
    files2 = {"file": ("data.csv", io.BytesIO(_csv_bytes(df)), "text/csv")}
    r2 = client.post("/api/ingest?source_name=demo", files=files2)
    assert r2.status_code in (200, 207)  # depending on your API
    payload = r2.json()
    assert payload.get("duplicates", 0) >= 2

    with SessionLocal() as s:
        # Should not double-insert; unique on (source_id, timestamp) or equivalent
        assert s.query(CleanEvent).count() == 2

        # ------------------ Invalid schema / input ------------------

def test_ingest_missing_timestamp_column(reset_db):
    df = pd.DataFrame([{"value": 10, "source": "demo"}])
    files = {"file": ("bad.csv", io.BytesIO(_csv_bytes(df)), "text/csv")}
    r = client.post("/api/ingest?source_name=demo", files=files)
    assert r.status_code == 400
    assert "timestamp" in r.json()["detail"].lower()

def test_ingest_missing_value_column(reset_db):
    df = pd.DataFrame([{"timestamp": "2024-01-01T00:00:00Z", "source": "demo"}])
    files = {"file": ("bad.csv", io.BytesIO(_csv_bytes(df)), "text/csv")}
    r = client.post("/api/ingest?source_name=demo", files=files)
    assert r.status_code == 400
    assert "value" in r.json()["detail"].lower()

def test_ingest_empty_file(reset_db):
    files = {"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
    r = client.post("/api/ingest?source_name=demo", files=files)
    assert r.status_code == 400

# ------------------ Transactional rollback ------------------

def test_ingest_partial_failure_triggers_rollback(reset_db):
    # First row valid, second row has bad timestamp -> whole request should fail
    df = pd.DataFrame([
        {"timestamp": "2024-01-05T00:00:00Z", "value": 10, "source": "demo"},
        {"timestamp": "not-a-timestamp", "value": 11, "source": "demo"},
    ])
    files = {"file": ("mix.csv", io.BytesIO(_csv_bytes(df)), "text/csv")}
    r = client.post("/api/ingest?source_name=demo", files=files)
    assert r.status_code == 400

    with SessionLocal() as s:
        assert s.query(CleanEvent).count() == 0
