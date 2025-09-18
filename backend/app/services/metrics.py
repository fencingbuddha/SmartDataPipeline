# backend/app/services/metrics.py
from __future__ import annotations
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models import MetricDaily  # adjust if your model path differs

def fetch_metric_daily(
    db: Session,
    *,
    source_id: int | None,
    metric: str | None,
    start_date: date | None,
    end_date: date | None,
    limit: int,
):
    stmt = select(MetricDaily)
    if source_id is not None:
        stmt = stmt.where(MetricDaily.source_id == source_id)
    if metric is not None:
        stmt = stmt.where(MetricDaily.metric == metric)
    if start_date is not None:
        stmt = stmt.where(MetricDaily.metric_date >= start_date)
    if end_date is not None:
        stmt = stmt.where(MetricDaily.metric_date <= end_date)
    stmt = stmt.order_by(MetricDaily.metric_date.asc()).limit(limit)
    return db.execute(stmt).scalars().all()

# --- If you want to return dicts instead of ORM objects, swap to this: ---
def fetch_metric_daily_as_dicts(
    db: Session,
    *,
    source_id: int | None,
    metric: str | None,
    start_date: date | None,
    end_date: date | None,
    limit: int,
):
    rows = fetch_metric_daily(
        db,
        source_id=source_id,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return [
        {
            "metric_date": r.metric_date,
            "source_id": r.source_id,
            "metric": r.metric,
            "value": r.value,
        }
        for r in rows
    ]
