from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.models.source import Source
from app.models.metric_daily import MetricDaily
from app.services.forecast import upsert_forecast_health

def _seed_series(db: Session, *, source_name="demo-source", metric="events_total", days=120, base=100.0):
    src = Source(name=source_name)
    db.add(src); db.commit(); db.refresh(src)
    start = date.today() - timedelta(days=days)
    for i in range(days):
        db.add(MetricDaily(
            source_id=src.id,
            metric=metric,
            metric_date=start + timedelta(days=i),
            value_sum=base + 0.2 * i,  # gentle trend
        ))
    db.commit()
    return src

def test_upsert_forecast_health_mape_threshold(db_session: Session):
    # NOTE: if your fixture is named differently, rename 'db_session' accordingly.
    src = _seed_series(db_session)
    fm = upsert_forecast_health(
        db_session,
        source_name=src.name,
        metric="events_total",
        window_n=90,
        horizon_n=7,
    )
    assert fm.mape is not None
    assert fm.mape <= 20.0  # baseline should be reasonably accurate on a smooth series
