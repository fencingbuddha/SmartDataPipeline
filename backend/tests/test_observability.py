from fastapi.testclient import TestClient


def test_request_id_header(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    header = resp.headers.get("x-request-id")
    assert header


def test_metrics_endpoint_exposed(client: TestClient):
    client.get("/api/health")
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text


def test_latency_health_stats(client: TestClient):
    for _ in range(3):
        client.get("/api/health")
    resp = client.get("/api/health/latency")
    assert resp.status_code == 200
    data = resp.json()
    assert "paths" in data and isinstance(data["paths"], list)
    entries = {p["path"]: p for p in data["paths"]}
    assert "/api/health" in entries
    row = entries["/api/health"]
    assert row["p95_ms"] >= row["p50_ms"]
    assert row["sample_size"] >= 1
