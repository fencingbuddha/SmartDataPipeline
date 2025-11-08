# app/services/metrics_fetch.py
from __future__ import annotations

from datetime import date
from typing import List, Optional

from sqlalchemy import and_, join, select
from sqlalchemy.orm import Session

from app.models.metric_daily import MetricDaily
from app.models.source import Source
from app.schemas.metrics import MetricDailyRow


def _normalize_sql_row(row) -> MetricDailyRow:
    metric_date_iso = row.metric_date.isoformat() if row.metric_date else None
    source_id = int(row.source_id) if row.source_id is not None else None
    value_sum = float(row.value_sum) if row.value_sum is not None else None
    value_avg = float(row.value_avg) if row.value_avg is not None else None
    value_count = int(row.value_count) if row.value_count is not None else None
    value_distinct = int(row.value_distinct) if row.value_distinct is not None else None

    return MetricDailyRow(
        metric_date=metric_date_iso,
        source_id=source_id,
        metric=row.metric,
        value_sum=value_sum,
        value_avg=value_avg,
        value_count=value_count,
        value_distinct=value_distinct,
        value=value_sum,
    )


def fetch_metric_daily(
    db: Session,
    *,
    metric: Optional[str] = None,
    source_id: Optional[int] = None,
    source_name: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: Optional[int] = None,
    order: str = "asc",
) -> List[MetricDailyRow]:
    """
    Fetch daily metric rows with flexible filtering.
    """
    j = join(MetricDaily, Source, MetricDaily.source_id == Source.id)
    conds = []

    if metric is not None:
        conds.append(MetricDaily.metric == metric)

    if source_id is not None:
        conds.append(MetricDaily.source_id == source_id)
    elif source_name:
        conds.append(Source.name == source_name)

    if start_date:
        conds.append(MetricDaily.metric_date >= start_date)
    if end_date:
        conds.append(MetricDaily.metric_date <= end_date)

    stmt = (
        select(
            MetricDaily.metric_date,
            MetricDaily.source_id,
            MetricDaily.metric,
            MetricDaily.value_sum,
            MetricDaily.value_avg,
            MetricDaily.value_count,
            MetricDaily.value_distinct,
        )
        .select_from(j)
        .where(and_(*conds))
    )

    if order.lower() == "desc":
        stmt = stmt.order_by(MetricDaily.metric_date.desc())
    else:
        stmt = stmt.order_by(MetricDaily.metric_date.asc())

    if limit and isinstance(limit, int) and limit > 0:
        stmt = stmt.limit(limit)

    rows = db.execute(stmt).all()
    return [_normalize_sql_row(r) for r in rows]


def fetch_metric_daily_as_dicts(
    db: Session,
    *,
    metric: Optional[str] = None,
    source_id: Optional[int] = None,
    source_name: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: Optional[int] = None,
    order: str = "asc",
) -> List[dict]:
    """
    Convenience wrapper for JSON serialization.
    """
    rows = fetch_metric_daily(
        db,
        metric=metric,
        source_id=source_id,
        source_name=source_name,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        order=order,
    )
    return [row.to_dict() for row in rows]


def fetch_metric_names(db: Session, *, source_name: Optional[str] = None) -> List[str]:
    """
    Return distinct metric names, optionally scoped by source_name.
    """
    j = join(MetricDaily, Source, MetricDaily.source_id == Source.id)

    if source_name:
        stmt = (
            select(MetricDaily.metric)
            .select_from(j)
            .where(Source.name == source_name)
            .distinct()
            .order_by(MetricDaily.metric.asc())
        )
    else:
        stmt = (
            select(MetricDaily.metric)
            .select_from(j)
            .distinct()
            .order_by(MetricDaily.metric.asc())
        )

    rows = db.execute(stmt).all()
    return [r.metric for r in rows]


__all__ = [
    "fetch_metric_daily",
    "fetch_metric_daily_as_dicts",
    "fetch_metric_names",
]
