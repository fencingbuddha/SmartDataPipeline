"""
Title: Ingest CSV -> Metrics available (UAT)
User Story: As a user, I can upload events so I can see daily metrics.
Created: 2025-10-07
Last Updated: 2025-10-08
"""
import time
from io import BytesIO
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.uat
client = TestClient(app)

SOURCE = "uat-source"
METRIC = "events_total"


def _unwrap_data(payload):
    if isinstance(payload, dict) and "ok" in payload and "data" in payload:
        return payload["data"]
    return payload


def _param_names_from_openapi(path: str):
    spec = app.openapi()
    p = spec.get("paths", {}).get(path, {})
    post = p.get("post") or {}
    params = post.get("parameters", [])
    names = {prm["name"] for prm in params if "name" in prm}
    return names


def _post_with_known_names(path: str, *, base: dict, d0: date, d1: date, accept=(200,201,202)):
    """
    Build params using the names the OpenAPI says the endpoint supports.
    Falls back to common variants if needed.
    """
    names = _param_names_from_openapi(path)
    params = dict(base)

    if "start_date" in names and "end_date" in names:
        params["start_date"] = d0.isoformat()
        params["end_date"] = d1.isoformat()
    elif "start" in names and "end" in names:
        params["start"] = d0.isoformat()
        params["end"] = d1.isoformat()

    resp = client.post(path, params=params)
    if resp.status_code in accept:
        return resp

    variants = [
        dict(params={**base, "start_date": d0.isoformat(), "end_date": d1.isoformat()}),
        dict(params={**base, "start": d0.isoformat(), "end": d1.isoformat()}),
        dict(params=base),
    ]
    last = resp
    for v in variants:
        r = client.post(path, **v)
        last = r
        if r.status_code in accept:
            return r
    raise AssertionError(f"{path} failed. Last={last.status_code} {last.text}")


def test_ingest_csv_then_metrics_visible():
    d0 = date.today()
    d1 = d0 + timedelta(days=1)

    csv = f"timestamp,value,metric,source\n{d0.isoformat()},3,{METRIC},{SOURCE}\n".encode()
    files = {"file": ("data.csv", BytesIO(csv), "text/csv")}
    r = client.post("/api/upload", params={"source_name": SOURCE}, files=files)
    assert r.status_code in (200, 201), r.text

    csv = f"timestamp,value,metric,source\n{d0.isoformat()},3,{METRIC},{SOURCE}\n".encode()
    files = {"file": ("data.csv", BytesIO(csv), "text/csv")}

    r_ing = client.post(
        "/api/ingest",
        params={"source_name": SOURCE, "default_metric": METRIC},
        files=files,
    )

    if r_ing.status_code not in (200, 201, 202):
        r_ing = client.post(
            "/api/ingest",
            params={"source_name": SOURCE, "default_metric": METRIC},
            json=[{
                "timestamp": d0.isoformat(),
                "value": 3,
                "metric": METRIC,
                "source": SOURCE,
            }],
        )

    assert r_ing.status_code in (200, 201, 202), r_ing.text

    base_kpi = {"source_name": SOURCE, "metric": METRIC}
    _post_with_known_names("/api/kpi/run", base=base_kpi, d0=d0, d1=d1)

    names = _param_names_from_openapi("/api/metrics/daily")
    params = {"source_name": SOURCE, "metric": METRIC}
    if "start_date" in names and "end_date" in names:
        params["start_date"] = d0.isoformat()
        params["end_date"] = d1.isoformat()
    elif "start" in names and "end" in names:
        params["start"] = d0.isoformat()
        params["end"] = d1.isoformat()

    found = []
    last_text = ""
    deadline = time.time() + 3.0
    while time.time() < deadline:
        resp = client.get("/api/metrics/daily", params=params)
        assert resp.status_code == 200, resp.text
        data = _unwrap_data(resp.json())
        if isinstance(data, list) and len(data) >= 1:
            found = data
            break
        last_text = resp.text
        time.sleep(0.15)

    assert len(found) >= 1, f"No daily KPI rows found. Last response: {last_text}"
