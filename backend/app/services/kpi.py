from __future__ import annotations
from datetime import date, datetime, time, timedelta, timezone
from collections import defaultdict
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.models import CleanEvent, MetricDaily, Source
from typing import Optional, Tuple, Dict, Any

def _utc_floor(d: date) -> datetime:
    return datetime.combine(d, time(0, 0, 0, tzinfo=timezone.utc))

def run_daily_kpis(
    db: Session,
    start: date | None = None,
    end: date | None = None,
    metric_name: str | None = None,
    source_id: int | None = None,
    agg: str | None = None,                 # <— added (currently not used)
    distinct_field: str | None = None,      # configurable distincts
) -> tuple[int, list[dict]]:
    # NOTE: 'agg' accepted for API compatibility; current implementation
    # computes value_sum/value_avg/value_count in one pass.

    mints, maxts = db.query(sa.func.min(CleanEvent.ts), sa.func.max(CleanEvent.ts)).one()
    if not mints or not maxts:
        return 0, []

    if start is None:
        start = mints.date()
    if end is None:
        end = maxts.date()
    if start > end:
        start, end = end, start

    start_dt = _utc_floor(start)
    end_dt   = _utc_floor(end + timedelta(days=1))

    # Prepare distinct column (if provided and valid)
    distinct_col = None
    if distinct_field and hasattr(CleanEvent, distinct_field): 
        distinct_col = getattr(CleanEvent, distinct_field)

    dialect = db.bind.dialect.name if db.bind is not None else ""

    results: list[tuple] = []
    if dialect == "postgresql":
        # group by UTC day to avoid TZ surprises
        day_utc = sa.cast(sa.func.date_trunc('day', sa.text("timezone('UTC', clean_events.ts)")), sa.Date)

        select_cols = [
            day_utc.label("metric_date"),
            CleanEvent.source_id,
            CleanEvent.metric,
            sa.func.sum(CleanEvent.value).label("value_sum"),
            sa.func.avg(CleanEvent.value).label("value_avg"),
            sa.func.count().label("value_count")        ]
        
        if distinct_col is not None:
            select_cols.append(sa.func.count(sa.distinct(distinct_col)).label("value_distinct"))

        q = (
            db.query(*select_cols)
              .filter(CleanEvent.ts >= start_dt, CleanEvent.ts < end_dt)
        )
        if metric_name:
            q = q.filter(CleanEvent.metric == metric_name)
        if source_id:
            q = q.filter(CleanEvent.source_id == source_id)

        q = q.group_by(day_utc, CleanEvent.source_id, CleanEvent.metric).order_by("metric_date")
        results = list(q.all())

        aggregates = []
        for r in results:
            row = {
                "metric_date": r.metric_date,
                "source_id":   r.source_id,
                "metric":      r.metric,
                "value_sum":   float(r.value_sum or 0),
                "value_avg":   float(r.value_avg or 0),
                "value_count": int(r.value_count or 0),
            }
            if distinct_col is not None:
                row["value_distinct"] = int(getattr(r, "value_distinct") or 0)
            aggregates.append(row)

    else:
        q = db.query(CleanEvent.ts, CleanEvent.source_id, CleanEvent.metric, CleanEvent.value)
        if distinct_col is not None:
            q = q.add_columns(distinct_col.label("distinct_key"))

        q = q.filter(CleanEvent.ts >= start_dt, CleanEvent.ts < end_dt)
        if metric_name:
            q = q.filter(CleanEvent.metric == metric_name)
        if source_id:
            q = q.filter(CleanEvent.source_id == source_id)

        events = q.all()
        if not events:
            return 0, []

        # agg[(day,sid,metric)] = running sums
        agg = defaultdict(lambda: {"sum": 0.0, "count": 0, "distincts": set()})
        # Support tuples of columns in future by normalizing to tuple
        for rec in events:
            if distinct_col is not None:
                ts, sid, metric, value, dkey = rec
            else:
                ts, sid, metric, value = rec
                dkey = None
            day = ts.astimezone(timezone.utc).date()
            key = (day, sid, metric)
            bucket = agg[key]
            bucket["sum"] += float(value or 0)
            bucket["count"] += 1
            if distinct_col is not None and dkey is not None:
                bucket["distincts"].add(dkey)

        aggregates = []
        for (metric_date, sid, metric), vals in agg.items():
            total = vals["sum"]; cnt = vals["count"]
            row = {
                "metric_date": metric_date,
                "source_id": sid,
                "metric": metric,
                "value_sum": total,
                "value_avg": (total / cnt) if cnt else 0.0,
                "value_count": cnt,
            }
            if distinct_col is not None:
                row["value_distinct"] = len(vals["distincts"])
            aggregates.append(row)

    # Upsert into MetricDaily
    if not aggregates:
        return 0, []

    upserted = 0
    preview: list[dict] = []

    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
        rows = []
        for row in aggregates:
            payload = {
                "metric_date": row["metric_date"],
                "source_id":   row["source_id"],
                "metric":      row["metric"],
                "value_sum":   float(row["value_sum"]),
                "value_avg":   float(row["value_avg"]),
                "value_count": int(row["value_count"]),
            }
            if "value_distinct" in row:
                payload["value_distinct"] = int(row["value_distinct"])
            rows.append(payload)

        stmt = insert(MetricDaily).values(rows)
        update_map = {
            "value_sum":   stmt.excluded.value_sum,
            "value_avg":   stmt.excluded.value_avg,
            "value_count": stmt.excluded.value_count,
        }
        if "value_distinct" in rows[0]:
            update_map["value_distinct"] = stmt.excluded.value_distinct

        stmt = stmt.on_conflict_do_update(
            index_elements=["metric_date", "source_id", "metric"],
            set_=update_map,
        )
        db.execute(stmt)
        db.commit()
        upserted = len(rows)
        preview = [
            {
                **{k: (str(v) if k == "metric_date" else v) for k, v in r.items()}
            } for r in rows
        ]
        return upserted, preview

    for row in aggregates:
        metric_date = row["metric_date"]
        sid         = row["source_id"]
        metric      = row["metric"]
        total       = float(row["value_sum"])
        avg         = float(row["value_avg"])
        cnt         = int(row["value_count"])
        dct         = int(row.get("value_distinct") or 0)

        md = (
            db.query(MetricDaily)
              .filter(
                  MetricDaily.metric_date == metric_date,
                  MetricDaily.source_id   == sid,
                  MetricDaily.metric      == metric,
              )
              .one_or_none()
        )
        if md is None:
            md = MetricDaily(
                metric_date=metric_date,
                source_id=sid,
                metric=metric,
                value_sum=total,
                value_avg=avg,
                value_count=cnt,
                value_distinct=dct if "value_distinct" in row else None,
            )
            db.add(md)
        else:
            md.value_sum   = total
            md.value_avg   = avg
            md.value_count = cnt
            if "value_distinct" in row:
                md.value_distinct = dct

        upserted += 1
        preview.append(
            {
                "metric_date": str(metric_date),
                "source_id": sid,
                "metric": metric,
                "value_sum": total,
                "value_avg": avg,
                "value_count": cnt,
                **({"value_distinct": dct} if "value_distinct" in row else {}),
            }
        )

    db.commit()
    return upserted, preview

def _resolve_source_id(db: Session, source_name: str) -> Optional[int]:
    return (
        db.query(Source.id)
          .filter(Source.name == source_name)
          .scalar()
    )

def _min_max_ts_for_metric(
    db: Session,
    source_id: int,
    metric: str,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    q = (
        db.query(sa.func.min(CleanEvent.ts), sa.func.max(CleanEvent.ts))
          .filter(CleanEvent.source_id == source_id, CleanEvent.metric == metric)
    )
    return q.one()

def run_kpi_for_metric(
    db: Session,
    *,
    source_name: str,
    metric: str,
    start: Optional[date] = None,
    end: Optional[date] = None,
    distinct_field: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Recompute MetricDaily rows for the given (source_name, metric) over [start, end].
    If start/end are not provided, it auto-detects the min/max days present
    in CleanEvent for that (source, metric) only.

    Returns:
      {
        "upserted": <int>,
        "metric": "<metric>",
        "source_name": "<source_name>",
        "start": "YYYY-MM-DD" | None,
        "end": "YYYY-MM-DD" | None,
        "preview": [ { metric_date, source_id, metric, value_sum, ... }, ... ]
      }
    """
    sid = _resolve_source_id(db, source_name)
    if sid is None:
        return {
            "upserted": 0,
            "metric": metric,
            "source_name": source_name,
            "start": None,
            "end": None,
            "preview": [],
            "message": f"Source '{source_name}' not found; nothing to compute.",
        }

    # If no explicit window, derive it from just this (source, metric)
    if start is None or end is None:
        mints, maxts = _min_max_ts_for_metric(db, sid, metric)
        if not mints or not maxts:
            return {
                "upserted": 0,
                "metric": metric,
                "source_name": source_name,
                "start": None,
                "end": None,
                "preview": [],
                "message": "No CleanEvent rows found for the given metric/source.",
            }
        if start is None:
            start = mints.date()
        if end is None:
            end = maxts.date()

    # Delegate to your existing daily aggregator (handles both PG and SQLite)
    upserted, preview = run_daily_kpis(
        db=db,
        start=start,
        end=end,
        metric_name=metric,
        source_id=sid,
        distinct_field=distinct_field,
    )

    return {
        "upserted": upserted,
        "metric": metric,
        "source_name": source_name,
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "preview": preview,  # already normalized in run_daily_kpis
    }
