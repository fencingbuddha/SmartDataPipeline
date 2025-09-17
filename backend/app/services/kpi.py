from datetime import date, datetime, time, timedelta
from typing import Optional, Tuple, List

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.clean_event import CleanEvent
from app.models.metric_daily import MetricDaily

def _get_timestamp_col():
    """
    Return the timestamp column from CleanEvent, preferring common names.
    Raises if none are found.
    """
    for cand in ("occurred_at", "event_time", "created_at", "timestamp", "ts"):
        if hasattr(CleanEvent, cand):
            return getattr(CleanEvent, cand)
    raise RuntimeError(
        "CleanEvent timestamp column not found. "
        "Expected one of: occurred_at, event_time, created_at, timestamp, ts."
    )


def _is_numeric_column(attr) -> bool:
    """Best-effort check whether a mapped column is numeric."""
    try:
        col = attr.property.columns[0]  # InstrumentedAttribute -> Column
        from sqlalchemy.sql.sqltypes import (Integer, BigInteger, SmallInteger, Float, Numeric, DECIMAL)
        return isinstance(col.type, (Integer, BigInteger, SmallInteger, Float, Numeric, DECIMAL))
    except Exception:
        return False


def run_daily_kpis(
    db: Session,
    start: Optional[date] = None,
    end: Optional[date] = None,
    *,
    metric_name: Optional[str] = None,  # <- NEW: optional override only used if CleanEvent.metric doesn't exist
) -> Tuple[int, List[dict]]:
    """
    Aggregate CleanEvents into MetricDaily with COUNT/SUM/AVG per (date, source_id, metric).

    - value_count = COUNT(*)
    - value_sum   = COALESCE(SUM(value), 0)   (only if value is numeric)
    - value_avg   = COALESCE(AVG(value), 0)   (only if value is numeric)

    Date window is inclusive at the day level: [start..end].
    Returns (rows_upserted, preview_rows[:10]).
    """
    if start and end and end < start:
        return 0, []

    # Timestamp column and day bucket (DB-agnostic: CAST(ts AS DATE))
    ts_col = _get_timestamp_col()
    dcol = sa.cast(ts_col, sa.Date).label("metric_date")

    # Metric expression:
    # - If CleanEvent has a "metric" column, group by it (preferred).
    # - Otherwise, use a literal name passed in (or "default").
    if hasattr(CleanEvent, "metric"):
        metric_expr = CleanEvent.metric.label("metric")
    else:
        metric_expr = sa.literal(metric_name or "default").label("metric")

    # Determine if we have a numeric 'value' column
    has_value_attr = hasattr(CleanEvent, "value")
    value_attr = getattr(CleanEvent, "value", None)
    value_is_numeric = has_value_attr and _is_numeric_column(value_attr)

    cols = [
        dcol,
        CleanEvent.source_id.label("source_id"),
        metric_expr,
    ]
    if value_is_numeric:
        cols += [
            sa.func.coalesce(sa.func.sum(value_attr), 0).label("value_sum"),
            sa.func.coalesce(sa.func.avg(value_attr), 0).label("value_avg"),
        ]
    else:
        cols += [
            sa.literal(0).label("value_sum"),
            sa.literal(0).label("value_avg"),
        ]
    cols.append(sa.func.count().label("value_count"))

    stmt = sa.select(*cols).group_by(dcol, CleanEvent.source_id, metric_expr)

    # Inclusive date filters
    if start:
        stmt = stmt.where(ts_col >= datetime.combine(start, time.min))
    if end:
        stmt = stmt.where(ts_col < datetime.combine(end + timedelta(days=1), time.min))

    rows = db.execute(stmt).all()
    if not rows:
        return 0, []

    # Upsert into metric_daily
    try:
        from sqlalchemy.dialects.postgresql import insert as pg_insert  # Postgres path

        ins = pg_insert(MetricDaily).values(
            [
                {
                    "metric_date": r.metric_date,
                    "source_id": r.source_id,
                    "metric": r.metric,
                    "value_sum": r.value_sum,
                    "value_avg": r.value_avg,
                    "value_count": r.value_count,
                }
                for r in rows
            ]
        )
        upsert = ins.on_conflict_do_update(
            index_elements=["metric_date", "source_id", "metric"],
            set_={
                "value_sum": ins.excluded.value_sum,
                "value_avg": ins.excluded.value_avg,
                "value_count": ins.excluded.value_count,
            },
        )
        db.execute(upsert)
    except Exception:
        # SQLite / non-PG fallback (or any driver issue): per-row merge
        for r in rows:
            db.merge(
                MetricDaily(
                    metric_date=r.metric_date,
                    source_id=r.source_id,
                    metric=r.metric,
                    value_sum=r.value_sum,
                    value_avg=r.value_avg,
                    value_count=int(r.value_count),
                )
            )

    db.commit()

    preview = [
        {
            "metric_date": str(r.metric_date),
            "source_id": r.source_id,
            "metric": r.metric,
            "value_sum": float(r.value_sum),
            "value_avg": float(r.value_avg),
            "value_count": int(r.value_count),
        }
        for r in rows[:10]
    ]
    return len(rows), preview
