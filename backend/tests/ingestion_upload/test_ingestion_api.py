from __future__ import annotations

import io
import json
from fastapi.testclient import TestClient
import pandas as pd

from app.main import app
from app.db import SessionLocal
from app.models import CleanEvent
from _helpers import unwrap

client = TestClient(app)


def _csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def _assert_error_contains(resp, substrings: tuple[str, ...]):
    """
    Accept either:
      - enveloped error: {"ok": false, "error": {"message": "..."}}
      - FastAPI default: {"detail": "..."}
    and assert any of the given substrings is present (case-insensitive).
    """
    body = resp.json()
    text = ""
    if isinstance(body, dict):
        if "error" in body and isinstance(body["error"], dict):
            text = (body["error"].get("message") or "") + " " + str(body["error"].get("code", ""))
        elif "detail" in body:
            text = str(body["detail"])
    assert any(s.lower() in text.lower() for s in substrings), f"Expected one of {substrings} in: {text!r}"


# ------------------ Happy paths ------------------

def test_ingest_csv_success(reset_db):
    df = pd.DataFrame([
        {"timestamp": "2024-01-01T00:00:00Z", "value": 10, "source": "demo"},
        {"timestamp": "2024-01-01T00:05:00Z", "value": 12, "source": "demo"},
    ])
    files = {"file": ("data.csv", io.BytesIO(_csv_bytes(df)), "text/csv")}
    r = client.post("/api/ingest?source_name=demo", files=files)
    assert r.status_code == 200, r.text
    data = unwrap(r.json())
    assert data.get("inserted") == 2

    with SessionLocal() as s:
        assert s.query(CleanEvent).count() == 2


def test_ingest_json_success(reset_db):
    records = [
        {"timestamp": "2024-01-02T00:00:00Z", "value": 5, "source": "demo"},
        {"timestamp": "2024-01-02T00:05:00Z", "value": 7, "source": "demo"},
    ]
    r = client.post("/api/ingest?source_name=demo", json=records)
    assert r.status_code == 200, r.text
    assert unwrap(r.json()).get("inserted") == 2


# ------------------ Duplicates / idempotency ------------------

def test_ingest_duplicate_records_ignored(reset_db):
    df = pd.DataFrame([
        {"timestamp": "2024-01-03T00:00:00Z", "value": 1, "source": "demo"},
        {"timestamp": "2024-01-03T00:01:00Z", "value": 2, "source": "demo"},
    ])
    files1 = {"file": ("data.csv", io.BytesIO(_csv_bytes(df)), "text/csv")}
    r1 = client.post("/api/ingest?source_name=demo", files=files1)
    assert r1.status_code == 200

    files2 = {"file": ("data.csv", io.BytesIO(_csv_bytes(df)), "text/csv")}
    r2 = client.post("/api/ingest?source_name=demo", files=files2)
    assert r2.status_code in (200, 207)
    payload = unwrap(r2.json())
    assert payload.get("duplicates", 0) >= 2

    with SessionLocal() as s:
        # Should not double-insert; unique on (source_id, timestamp) or equivalent
        assert s.query(CleanEvent).count() == 2


# ------------------ Invalid schema / input ------------------

def test_ingest_missing_timestamp_column(reset_db):
    df = pd.DataFrame([{"value": 10, "source": "demo"}])
    files = {"file": ("bad.csv", io.BytesIO(_csv_bytes(df)), "text/csv")}
    r = client.post("/api/ingest?source_name=demo", files=files)
    assert r.status_code == 400, r.text
    _assert_error_contains(r, ("timestamp", "time", "date"))


def test_ingest_missing_value_column(reset_db):
    df = pd.DataFrame([{"timestamp": "2024-01-01T00:00:00Z", "source": "demo"}])
    files = {"file": ("bad.csv", io.BytesIO(_csv_bytes(df)), "text/csv")}
    r = client.post("/api/ingest?source_name=demo", files=files)
    assert r.status_code == 400, r.text
    _assert_error_contains(r, ("value", "numeric"))


def test_ingest_empty_file(reset_db):
    files = {"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
    r = client.post("/api/ingest?source_name=demo", files=files)
    assert r.status_code == 400, r.text
    _assert_error_contains(r, ("empty file", "no data", "empty"))


# ------------------ Transactional rollback ------------------

def test_ingest_partial_failure_triggers_rollback(reset_db):
    # First row valid, second row has bad timestamp -> whole request should fail
    df = pd.DataFrame([
        {"timestamp": "2024-01-05T00:00:00Z", "value": 10, "source": "demo"},
        {"timestamp": "not-a-timestamp", "value": 11, "source": "demo"},
    ])
    files = {"file": ("mix.csv", io.BytesIO(_csv_bytes(df)), "text/csv")}
    r = client.post("/api/ingest?source_name=demo", files=files)
    assert r.status_code == 400, r.text

    with SessionLocal() as s:
        assert s.query(CleanEvent).count() == 0
