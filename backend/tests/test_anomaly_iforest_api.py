# backend/tests/test_anomaly_iforest_api.py
from datetime import date, timedelta
import pandas as pd
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_anomaly_iforest_endpoint_happy(monkeypatch):
    # Prepare a tiny deterministic DF with one spike
    start = date(2024, 1, 1)
    days = [start + timedelta(days=i) for i in range(30)]
    values = [100.0] * 30
    values[10] = 145.0  # spike
    df = pd.DataFrame({"metric_date": pd.to_datetime(days), "value": values})

    # Monkeypatch the fetcher used by the router; allow creating it if missing
    from app.services import metrics as metrics_service
    monkeypatch.setattr(
        metrics_service,
        "fetch_metric_daily_as_df",
        lambda **kwargs: df,
        raising=False,
    )

    resp = client.get(
        "/api/metrics/anomaly/iforest",
        params=dict(
            source_name="demo-source",
            metric="events_total",
            start_date=str(days[0]),
            end_date=str(days[-1]),
            contamination=0.05,
            n_estimators=150,
        ),
    )
    assert resp.status_code == 200
    body = resp.json()
    points = body["points"]
    assert len(points) == 30
    flagged_idxs = [i for i, p in enumerate(points) if p["is_outlier"]]
    assert 10 in flagged_idxs, f"Expected index 10 flagged, got {flagged_idxs}"


def test_anomaly_iforest_missing_helper(monkeypatch):
    # Simulate helper not implemented → 500
    from app.services import metrics as metrics_service
    if hasattr(metrics_service, "fetch_metric_daily_as_df"):
        monkeypatch.delattr(metrics_service, "fetch_metric_daily_as_df")

    resp = client.get(
        "/api/metrics/anomaly/iforest",
        params=dict(
            source_name="demo-source",
            metric="events_total",
            start_date="2024-01-01",
            end_date="2024-01-10",
        ),
    )
    assert resp.status_code == 500
    assert "fetch_metric_daily_as_df" in resp.text


def test_anomaly_iforest_unknown_source(monkeypatch):
    # Return None to indicate unknown source/metric → 404
    from app.services import metrics as metrics_service
    monkeypatch.setattr(
        metrics_service,
        "fetch_metric_daily_as_df",
        lambda **kwargs: None,
        raising=False,
    )

    resp = client.get(
        "/api/metrics/anomaly/iforest",
        params=dict(
            source_name="nope",
            metric="events_total",
            start_date="2024-01-01",
            end_date="2024-01-10",
        ),
    )
    assert resp.status_code == 404
