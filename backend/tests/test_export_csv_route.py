# backend/tests/test_export_csv_route.py
import re
from fastapi.testclient import TestClient

from app.main import app  # adjust if your entry is elsewhere

client = TestClient(app)

def test_export_csv_route_ok(monkeypatch):
    # If your test DB requires seed, patch the service to return a tiny CSV.
    # Otherwise, delete this monkeypatch and rely on your shared test fixtures.
    from app.routers import metrics as metrics_router

    def _fake_csv(*args, **kwargs) -> str:
        return "metric_date,source_id,metric,value\n2025-01-01,1,events_total,100\n"

    # If your handler builds CSV directly, adapt the monkeypatch target accordingly.
    if hasattr(metrics_router, "generate_csv"):
        monkeypatch.setattr(metrics_router, "generate_csv", _fake_csv)

    r = client.get(
        "/api/metrics/export/csv",
        params=dict(source_name="demo-source", metric="events_total", start="2025-01-01", end="2025-01-07"),
    )
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    # filename present
    disp = r.headers.get("content-disposition", "")
    assert "attachment;" in disp
    assert ".csv" in disp

    # basic CSV sanity (allow header-only when no rows in range)
    body = r.text.strip().splitlines()
    assert len(body) >= 1
    assert re.match(r"^metric_date,.*value", body[0])
    if len(body) > 1:
        # first data row should begin with an ISO date (YYYY-MM-DD)
        assert re.match(r"^\d{4}-\d{2}-\d{2}", body[1].split(",")[0])