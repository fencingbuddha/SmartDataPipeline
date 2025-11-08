from datetime import date

from app.services.metrics_fetch import fetch_metric_daily, fetch_metric_daily_as_dicts
from app.models import MetricDaily, Source

def _seed(db):
    s1 = Source(name="seed-src-1")
    s2 = Source(name="seed-src-2")
    db.add_all([s1, s2])
    db.flush()

    db.add_all([
        MetricDaily(metric_date=date(2025, 9, 15), source_id=s1.id, metric="events_total", value=100),
        MetricDaily(metric_date=date(2025, 9, 16), source_id=s1.id, metric="events_total", value=120),
        MetricDaily(metric_date=date(2025, 9, 16), source_id=s2.id, metric="events_total", value=50),
    ])
    db.commit()
    return s1.id, s2.id

def test_fetch_metric_daily_filters(db, reset_db):
    s1_id, _ = _seed(db)
    rows = fetch_metric_daily(
        db,
        source_id=s1_id,
        metric="events_total",
        start_date=date(2025, 9, 15),
        end_date=date(2025, 9, 16),
        limit=100,
    )
    assert [r.value for r in rows] == [100, 120]

def test_fetch_metric_daily_as_dicts(db, reset_db):
    _seed(db)
    out = fetch_metric_daily_as_dicts(
        db,
        source_id=None,
        metric=None,
        start_date=None,
        end_date=None,
        limit=10,
    )
    assert isinstance(out, list) and len(out) == 3
    assert {"metric_date", "source_id", "metric", "value"} <= set(out[0].keys())
