# app/services/kpi.py
from datetime import date, datetime, time, timedelta
from typing import Optional, Tuple, List

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.clean_event import CleanEvent
from app.models.metric_daily import MetricDaily

def _get_timestamp_col():
    # Prefer occurred_at; fall back to typical names
    for cand in ("occurred_at", "event_time", "created_at", "timestamp", "ts"):
        if hasattr(CleanEvent, cand):
            return getattr(CleanEvent, cand)
    raise RuntimeError(
        "CleanEvent timestamp column not found. "
        "Expected one of: occurred_at, event_time, created_at, timestamp, ts."
    )

def run_daily_kpis(
    db: Session,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> Tuple[int, List[dict]]:
    ts_col = CleanEvent.ts

    # build date column
    dcol = sa.cast(sa.func.date_trunc("day", ts_col), sa.Date).label("metric_date")

    # does CleanEvent have a numeric 'value' column?
    has_value = hasattr(CleanEvent, "value")
    value_col = getattr(CleanEvent, "value", None)

    cols = [dcol, CleanEvent.source_id, CleanEvent.metric]

    if has_value:
        cols.extend([
            sa.func.sum(value_col).label("value_sum"),
            sa.func.avg(value_col).label("value_avg"),
        ])
    else:
        cols.extend([
            sa.literal(0).label("value_sum"),
            sa.literal(0).label("value_avg"),
        ])

    cols.append(sa.func.count().label("value_count"))

    stmt = sa.select(*cols).group_by(dcol, CleanEvent.source_id, CleanEvent.metric)

    # date filters (inclusive)
    if start:
        stmt = stmt.where(ts_col >= datetime.combine(start, time.min))
    if end:
        stmt = stmt.where(ts_col < datetime.combine(end + timedelta(days=1), time.min))

    rows = db.execute(stmt).all()
    if not rows:
        return 0, []

    # upsert into metric_daily
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    ins = pg_insert(MetricDaily).values([
        dict(
            metric_date=r.metric_date,
            source_id=r.source_id,
            metric=r.metric,
            value_sum=r.value_sum,
            value_avg=r.value_avg,
            value_count=r.value_count,
        )
        for r in rows
    ])
    upsert = ins.on_conflict_do_update(
        index_elements=[MetricDaily.metric_date, MetricDaily.source_id, MetricDaily.metric],
        set_={
            "value_sum":  ins.excluded.value_sum,
            "value_avg":  ins.excluded.value_avg,
            "value_count":ins.excluded.value_count,
        },
    )

    db.execute(upsert)
    db.commit()

    preview = [
        dict(
            metric_date=str(r.metric_date),
            source_id=r.source_id,
            metric=r.metric,
            value_sum=float(r.value_sum),
            value_avg=float(r.value_avg),
            value_count=int(r.value_count),
        ) for r in rows[:10]
    ]
    return len(rows), preview
