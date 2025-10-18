# app/services/metrics.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from typing import Iterable, List, Optional, Union

from sqlalchemy import and_, select, join
from sqlalchemy.orm import Session

from app.models.metric_daily import MetricDaily
from app.models.source import Source


@dataclass
class MetricDailyRow(dict):
    """
    Dict-like row that ALSO supports attribute access (r.value, r.metric_date, ...).
    """
    __slots__ = ()

    def __init__(self, **kwargs):
        # Accept only keyword args for clarity, then init the dict
        super().__init__(**kwargs)

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as ex:
            raise AttributeError(name) from ex

    def to_dict(self) -> dict:
        return dict(self)

def _normalize_sql_row(r) -> MetricDailyRow:
    metric_date_iso = r.metric_date.isoformat() if r.metric_date else None
    source_id = int(r.source_id) if r.source_id is not None else None
    value_sum = float(r.value_sum) if r.value_sum is not None else None
    value_avg = float(r.value_avg) if r.value_avg is not None else None
    value_count = int(r.value_count) if r.value_count is not None else None
    value_distinct = int(r.value_distinct) if r.value_distinct is not None else None

    return MetricDailyRow(
        metric_date=metric_date_iso,
        source_id=source_id,
        metric=r.metric,
        value_sum=value_sum,
        value_avg=value_avg,
        value_count=value_count,
        value_distinct=value_distinct,
        value=value_sum,  # by convention
    )

# change the signature: metric is Optional
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

    If `metric` is None, no metric-name filter is applied (used by tests).
    """
    j = join(MetricDaily, Source, MetricDaily.source_id == Source.id)
    conds = []                              # was: [MetricDaily.metric == metric]

    # add metric filter only when provided
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
    metric: str,
    source_id: Optional[int] = None,
    source_name: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: Optional[int] = None,
    order: str = "asc",
) -> List[dict]:
    """
    Convenience wrapper: returns list of dicts for easy JSON serialization.
    Used by routers.
    """
    objs = fetch_metric_daily(
        db,
        metric=metric,
        source_id=source_id,
        source_name=source_name,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        order=order,
    )
    return [o.to_dict() for o in objs]


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


def to_csv(rows: Iterable[Union[MetricDailyRow, dict]]) -> str:
    """
    Serialize rows to CSV with the expected columns.
    Accepts either MetricDailyRow objects or dicts with equivalent keys.
    """
    header = [
        "metric_date",
        "source_id",
        "metric",
        "value",        # mirrors value_sum
        "value_count",
        "value_sum",
        "value_avg",
    ]
    lines = [",".join(header)]

    def _get(row, key):
        if isinstance(row, MetricDailyRow):
            return getattr(row, key)
        return row.get(key)

    def _fmt(v):
        return "" if v is None else str(v)

    for r in rows:
        lines.append(
            ",".join(
                [
                    _fmt(_get(r, "metric_date")),
                    _fmt(_get(r, "source_id")),
                    _fmt(_get(r, "metric")),
                    _fmt(_get(r, "value")),
                    _fmt(_get(r, "value_count")),
                    _fmt(_get(r, "value_sum")),
                    _fmt(_get(r, "value_avg")),
                ]
            )
        )

    return "\n".join(lines)
