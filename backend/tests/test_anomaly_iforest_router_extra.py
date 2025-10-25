from __future__ import annotations

import json
from datetime import date, timedelta
from sqlalchemy import text

from app.routers import anomaly_iforest


def _seed_metric_daily(db, source_name: str, metric: str, values: list[float], start: date | None = None):
    start = start or date(2024, 1, 1)
    db.execute(text("INSERT INTO sources (name) VALUES (:name)"), {"name": source_name})
    db.commit()
    source_id = db.execute(text("SELECT id FROM sources WHERE name = :name"), {"name": source_name}).scalar_one()

    rows = []
    day = start
    for value in values:
        rows.append(
            {
                "metric_date": day.isoformat(),
                "source_id": source_id,
                "metric": metric,
                "value": value,
                "value_sum": value,
                "value_avg": value,
                "value_count": 1,
                "value_distinct": None,
            }
        )
        day += timedelta(days=1)
    db.execute(
        text(
            """
            INSERT INTO metric_daily (metric_date, source_id, metric, value, value_sum, value_avg, value_count, value_distinct)
            VALUES (:metric_date, :source_id, :metric, :value, :value_sum, :value_avg, :value_count, :value_distinct)
            """
        ),
        rows,
    )
    db.commit()
    return source_id


def test_anomaly_iforest_unknown_source_returns_error(db):
    response = anomaly_iforest.anomaly_iforest(
        source_name="missing",
        source_id=None,
        metric="events",
        start_date=None,
        end_date=None,
        contamination=0.05,
        db=db,
    )
    assert response.status_code == 404
    payload = json.loads(response.body)
    assert payload["error"]["code"] == "UNKNOWN_SOURCE"


def test_anomaly_iforest_insufficient_data_path(db):
    _seed_metric_daily(db, "few-points", "events", [1, 2, 3, 4])

    response = anomaly_iforest.anomaly_iforest(
        source_name="few-points",
        source_id=None,
        metric="events",
        start_date=None,
        end_date=None,
        contamination=0.05,
        db=db,
    )
    assert response.status_code == 200
    payload = json.loads(response.body)
    assert payload["ok"] is True
    assert payload["meta"]["params"]["reason"] == "insufficient_data"
    assert len(payload["data"]["points"]) == 4


def test_anomaly_iforest_falls_back_to_rolling_z_when_model_fails(db, monkeypatch):
    _seed_metric_daily(db, "fallback-source", "events", [1, 2, 3, 4, 5, 6, 7])

    from sklearn.ensemble import IsolationForest

    def _fail_fit(self, X):
        raise RuntimeError("boom")

    monkeypatch.setattr(IsolationForest, "fit", _fail_fit, raising=False)

    response = anomaly_iforest.anomaly_iforest(
        source_name="fallback-source",
        source_id=None,
        metric="events",
        start_date=None,
        end_date=None,
        contamination=0.05,
        db=db,
    )
    assert response.status_code == 200
    payload = json.loads(response.body)
    assert payload["meta"]["params"]["method"] == "rolling_z (fallback)"
    assert len(payload["data"]["points"]) == 7
