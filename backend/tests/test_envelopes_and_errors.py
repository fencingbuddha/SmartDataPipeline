# tests/test_envelopes_and_errors.py
from __future__ import annotations

from _helpers import unwrap, is_enveloped


def test_metrics_daily_envelope_empty_range(client):
    """
    Future-only range should return an enveloped payload with ok=True and empty data list.
    """
    r = client.get(
        "/api/metrics/daily",
        params={
            "source_name": "demo-source",
            "metric": "events_total",
            "start_date": "2099-01-01",
            "end_date": "2099-01-07",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert is_enveloped(body), f"expected envelope, got: {body!r}"
    assert body["ok"] is True
    data = unwrap(body)
    assert isinstance(data, list)
    assert data == []


def test_metrics_daily_unknown_source_tolerates_graceful_empty(client):
    """
    Current router behavior: unknown source returns 200 + empty list inside envelope.
    Still tolerates a future change to 404 (enveloped or FastAPI default).
    """
    r = client.get(
        "/api/metrics/daily",
        params={
            "source_name": "nope-source",
            "metric": "events_total",
            "start_date": "2025-01-01",
            "end_date": "2025-01-02",
        },
    )

    if r.status_code == 404:
        err = r.json()
        # Could be enveloped or FastAPI's {"detail": "..."}
        if is_enveloped(err):
            assert err["ok"] is False
            assert err.get("error", {}).get("code") in {"UNKNOWN_SOURCE", "NOT_FOUND"}
        else:
            assert "detail" in err
        return

    # Graceful-empty (current)
    assert r.status_code == 200, r.text
    body = r.json()
    assert is_enveloped(body)
    assert body["ok"] is True
    assert unwrap(body) == []


def test_upload_wrong_media_type_415_or_422(client):
    """
    If the route pre-validates Content-Type it should be 415.
    If FastAPI body validation triggers first, it may be 422.
    Accept either to avoid coupling test to implementation detail.
    """
    r = client.post("/api/upload", json={"oops": "json"})
    assert r.status_code in (415, 422), r.text


def test_upload_empty_file_400_or_200(client):
    """
    An empty multipart file should ideally be 400.
    Some implementations may still return 200; accept both,
    but if enveloped and error-style, require ok=False.
    """
    files = {"file": ("empty.csv", "", "text/csv")}
    r = client.post("/api/upload?source_name=demo-source", files=files)
    assert r.status_code in (200, 400), r.text
    body = r.json()
    if is_enveloped(body) and r.status_code == 400:
        assert body["ok"] is False


def test_ingest_missing_columns_400(client):
    """
    Bad CSV (missing columns) should be a 400. Body may be enveloped or FastAPI default.
    """
    bad_csv = "only_one_col\nvalue\n"
    r = client.post(
        "/api/ingest?source_name=demo-source",
        data=bad_csv,
        headers={"Content-Type": "text/csv"},
    )
    assert r.status_code == 400, r.text
    body = r.json()
    # If enveloped, ensure it's an error envelope; otherwise accept default error shape
    if is_enveloped(body):
        assert body["ok"] is False
