from datetime import date, timedelta

from app.models.metric_daily import MetricDaily
from app.models.source import Source
from app.services import forecast_reliability as reliability_service


def _seed_metric_series(db, source_name: str, metric: str, values: list[float]) -> Source:
    """Insert a Source row and matching metric_daily records for the provided series."""
    source = Source(name=source_name)
    db.add(source)
    db.commit()
    db.refresh(source)

    start = date.today() - timedelta(days=len(values) - 1)
    for offset, val in enumerate(values):
        db.add(
            MetricDaily(
                metric_date=start + timedelta(days=offset),
                source_id=source.id,
                metric=metric,
                value_sum=float(val),
                value_avg=float(val),
                value_count=1,
            )
        )
    db.commit()
    return source


def test_load_metric_series_returns_chronological_values(db):
    source_name = "svc-series-src"
    metric = "svc-series-metric"
    values = [15.0, 18.0, 21.0]
    _seed_metric_series(db, source_name, metric, values)

    series = reliability_service._load_metric_series(db, source_name, metric, days=10)
    assert series == values


def test_run_reliability_generates_folds_and_metrics(db):
    source_name = "svc-run-src"
    metric = "svc-run-metric"
    values = [float(40 + i) for i in range(30)]
    _seed_metric_series(db, source_name, metric, values)

    rec = reliability_service.run_reliability(
        db,
        source_name=source_name,
        metric=metric,
        days=30,
        folds=5,
        horizon=3,
    )

    assert rec.source_name == source_name
    assert rec.metric == metric
    assert 0 <= rec.score <= 100
    assert rec.mape >= 0.0
    assert rec.rmse >= 0.0
    assert rec.smape >= 0.0
    assert len(rec.folds) > 0
    # Fold indices should be sequential starting at zero
    assert {f.fold_index for f in rec.folds} == set(range(len(rec.folds)))
    assert all(f.mae >= 0.0 and f.rmse >= 0.0 for f in rec.folds)
