from __future__ import annotations
from datetime import date, datetime, time, timedelta, timezone
from collections import defaultdict
import sqlalchemy as sa
from sqlalchemy.orm import Session
from app.models import CleanEvent, MetricDaily

def _utc_floor(d: date) -> datetime:
    return datetime.combine(d, time(0, 0, 0, tzinfo=timezone.utc))

def run_daily_kpis(
    db: Session,
    start: date | None = None,
    end: date | None = None,
    metric_name: str | None = None,
    source_id: int | None = None,
) -> tuple[int, list[dict]]:
    # derive window from data if not given
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

    # --- Preferred: SQL aggregation (Postgres); fallback: Python loop (SQLite, etc.) ---
    dialect = db.bind.dialect.name if db.bind is not None else ""

    results: list[tuple] = []
    if dialect == "postgresql":
        # group by UTC day to avoid TZ surprises
        # date_trunc('day', ts AT TIME ZONE 'UTC') :: date
        day_utc = sa.cast(sa.func.date_trunc('day', sa.text("timezone('UTC', clean_events.ts)")), sa.Date)

        q = (
            db.query(
                day_utc.label("metric_date"),
                CleanEvent.source_id,
                CleanEvent.metric,
                sa.func.sum(CleanEvent.value).label("value_sum"),
                sa.func.avg(CleanEvent.value).label("value_avg"),
                sa.func.count(CleanEvent.value).label("value_count"),
            )
            .filter(CleanEvent.ts >= start_dt, CleanEvent.ts < end_dt)
        )
        if metric_name:
            q = q.filter(CleanEvent.metric == metric_name)
        if source_id:
            q = q.filter(CleanEvent.source_id == source_id)

        q = q.group_by(day_utc, CleanEvent.source_id, CleanEvent.metric).order_by("metric_date")
        results = list(q.all())

        # convert rows into a uniform iterable of dicts for upsert
        aggregates = [
            {
                "metric_date": r.metric_date,
                "source_id":   r.source_id,
                "metric":      r.metric,
                "value_sum":   float(r.value_sum or 0),
                "value_avg":   float(r.value_avg or 0),
                "value_count": int(r.value_count or 0),
            }
            for r in results
        ]
    else:
        # Fallback: Python aggregation (keeps your original logic)
        q = db.query(CleanEvent.ts, CleanEvent.source_id, CleanEvent.metric, CleanEvent.value)\
              .filter(CleanEvent.ts >= start_dt, CleanEvent.ts < end_dt)
        if metric_name:
            q = q.filter(CleanEvent.metric == metric_name)
        if source_id:
            q = q.filter(CleanEvent.source_id == source_id)

        events = q.all()
        if not events:
            return 0, []

        agg = defaultdict(lambda: {"sum": 0.0, "count": 0})
        for ts, sid, metric, value in events:
            day = ts.astimezone(timezone.utc).date()  # ensure UTC day
            key = (day, sid, metric)
            agg[key]["sum"] += float(value or 0)
            agg[key]["count"] += 1

        aggregates = []
        for (metric_date, sid, metric), vals in agg.items():
            total = vals["sum"]
            cnt   = vals["count"]
            aggregates.append({
                "metric_date": metric_date,
                "source_id": sid,
                "metric": metric,
                "value_sum": total,
                "value_avg": (total / cnt) if cnt else 0.0,
                "value_count": cnt,
            })
    print("DEBUG aggregates:", aggregates)

    # Upsert into MetricDaily
    if not aggregates:
        return 0, []

    upserted = 0
    preview: list[dict] = []
    for row in aggregates:
        metric_date = row["metric_date"]
        sid         = row["source_id"]
        metric      = row["metric"]
        total       = float(row["value_sum"])
        avg         = float(row["value_avg"])
        cnt         = int(row["value_count"])

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
            )
            db.add(md)
        else:
            md.value_sum = total
            md.value_avg = avg
            md.value_count = cnt

        upserted += 1
        preview.append(
            {
                "metric_date": str(metric_date),
                "source_id": sid,
                "metric": metric,
                "value_sum": total,
                "value_avg": avg,
                "value_count": cnt,
            }
        )

    db.commit()
    return upserted, preview
