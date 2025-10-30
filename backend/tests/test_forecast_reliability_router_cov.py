import json
from datetime import date

import pytest
from fastapi import HTTPException

from app.models.metric_daily import MetricDaily
from app.models.source import Source
from app.routers.forecast_reliability import RunIn, read_reliability, run_recalc


def test_read_reliability_missing_raises_http_exception(db):
    with pytest.raises(HTTPException) as exc:
        read_reliability(source_name="missing-source", metric="missing-metric", db=db)
    assert exc.value.status_code == 404
    assert exc.value.detail == "No reliability computed yet"


def test_run_recalc_succeeds_with_seeded_data(db, seeded_metric_daily):
    body = RunIn(
        source_name=seeded_metric_daily["source_name"],
        metric=seeded_metric_daily["metric"],
        days=60,
        folds=5,
        horizon=7,
    )

    response = run_recalc(body=body, db=db)
    assert response.status_code == 200

    payload = json.loads(response.body)
    assert payload["ok"] is True
    assert payload["data"]["folds"] > 0
    assert payload["meta"]["source_name"] == seeded_metric_daily["source_name"]
    assert payload["meta"]["metric"] == seeded_metric_daily["metric"]


def test_run_recalc_raises_when_no_folds(db):
    source = Source(name="sparse-source")
    db.add(source)
    db.commit()
    db.refresh(source)

    db.add(
        MetricDaily(
            metric_date=date.today(),
            source_id=source.id,
            metric="sparse-metric",
            value_sum=5.0,
            value_avg=5.0,
            value_count=1,
        )
    )
    db.commit()

    body = RunIn(
        source_name=source.name,
        metric="sparse-metric",
        days=7,
        folds=5,
        horizon=3,
    )

    with pytest.raises(HTTPException) as exc:
        run_recalc(body=body, db=db)

    assert exc.value.status_code == 422
    assert "produced 0 folds" in exc.value.detail
