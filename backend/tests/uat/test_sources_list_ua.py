"""
Title: Sources list includes newly ingested source (UAT)
User Story: After ingesting data, I can discover the source via the sources API.
"""
from datetime import date
import json
import time
from io import BytesIO  # kept in case other UATs import this file's names

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.uat
client = TestClient(app)


def _unwrap_data(payload):
    if isinstance(payload, dict) and "ok" in payload and "data" in payload:
        return payload["data"]
    return payload


def _list_source_names():
    """Return a flat list of source names from /api/sources, handling both shapes."""
    resp = client.get("/api/sources")
    assert resp.status_code == 200, resp.text
    data = _unwrap_data(resp.json())
    assert isinstance(data, list), f"Unexpected payload shape: {data!r}"
    names = []
    for item in data:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and "name" in item:
            names.append(item["name"])
    return names


def test_sources_list_contains_source_after_ingest():
    source = "uat-source-listing"
    metric = "events_total"

    # Ingest a trivial JSON payload so the source exists in the DB
    today = date.today().isoformat()
    events = [{"timestamp": today, "value": 1, "metric": metric, "source": source}]

    r = client.post(
        "/api/ingest",
        params={"source_name": source},
        content=json.dumps(events),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code in (200, 201), r.text

    # Briefly poll /api/sources in case creation is async/transactional
    deadline = time.time() + 2.0
    names = []
    while time.time() < deadline:
        names = _list_source_names()
        if source in names:
            break
        time.sleep(0.1)

    assert source in names, f"Expected '{source}' in sources list; got {names!r}"
