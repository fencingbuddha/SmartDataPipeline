import io, json

def test_ingest_csv_success(client):
    csv = b"timestamp,metric,value\n2025-09-01,sales,100\n2025-09-02,sales,200\n"
    files = {"file": ("sample.csv", io.BytesIO(csv), "text/csv")}
    r = client.post("/api/ingest?source_name=tcsv", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "tcsv"
    assert body["raw_events_inserted"] == 2
    assert body["clean_events_inserted"] == 2

def test_ingest_json_success(client):
    payload = [
        {"timestamp": "2025-09-01", "metric": "clicks", "value": 10},
        {"timestamp": "2025-09-02", "metric": "clicks", "value": 12.5},
    ]
    fb = io.BytesIO(json.dumps(payload).encode("utf-8"))
    files = {"file": ("data.json", fb, "application/json")}
    r = client.post("/api/ingest?source_name=tjson", files=files)
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
