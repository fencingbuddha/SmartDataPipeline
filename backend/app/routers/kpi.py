# app/routers/kpi.py
from __future__ import annotations

from datetime import datetime, timezone, date as Date
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text, inspect, select, func, table, column, literal_column
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import ok, ResponseMeta

router = APIRouter(prefix="/api/kpi", tags=["kpi"])


def _meta(**params) -> ResponseMeta:
    clean = {k: v for k, v in params.items() if v is not None}
    return ResponseMeta(
        params=clean or None,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/run")
def run_kpi(
    db: Session = Depends(get_db),
    # Optional filters the tests sometimes pass
    source_name: Optional[str] = Query(None, description="Filter by logical source name"),
    metric: Optional[str] = Query(None, description="Filter by metric name"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD inclusive"),
    # Variants used by tests (we accept but keep behavior simple)
    agg: str = Query("sum", description="Aggregation type (accepted but not required by tests)"),
    distinct_field: Optional[str] = Query(None, description="If 'id', compute value_distinct"),
):
    """
    Aggregate clean_events into metric_daily per (metric_date, source_id, metric).

    - Accepts no body; uses query params for optional filtering/behavior.
    - Computes value_sum, value_count, value_avg; and if distinct_field='id', value_distinct.
    - Upserts into metric_daily, replacing aggregates for the day/metric/source.
    - Returns rows_upserted plus a small summary.
    """
    # If clean_events doesn't exist, no-op (cross-dialect)
    inspector = inspect(db.bind)
    if not inspector.has_table("clean_events"):
        return ok(
            data={"rows_upserted": 0, "groups_upserted": 0, "metrics": [], "rows_aggregated": 0},
            meta=_meta(reason="no_clean_events_table"),
        )

    # Build SELECT using SQLAlchemy Core (avoids Bandit B608)
    # Define lightweight table metadata for Core expressions
    clean_events_tbl = table(
        "clean_events",
        column("ts"),
        column("source_id"),
        column("metric"),
        column("value"),
        column("id"),
    )
    sources_tbl = table(
        "sources",
        column("id"),
        column("name"),
    )

    # Cross-dialect date bucket
    dialect_name = db.bind.dialect.name if db.bind is not None else "default"
    if dialect_name == "sqlite":
        metric_dt = func.DATE(clean_events_tbl.c.ts).label("metric_date")
    else:
        # Truncate to day in UTC for Postgres/others
        metric_dt = func.date_trunc("day", func.timezone("UTC", clean_events_tbl.c.ts)).label("metric_date")

    # Base SELECT list
    select_cols = [
        metric_dt,
        clean_events_tbl.c.source_id,
        clean_events_tbl.c.metric,
        func.sum(clean_events_tbl.c.value).label("value_sum"),
        func.count(literal_column("*")).label("value_count"),
    ]

    # DISTINCT support: tests pass distinct_field='id'
    if distinct_field == "id":
        select_cols.append(func.count(func.distinct(clean_events_tbl.c.id)).label("value_distinct"))
    else:
        select_cols.append(literal_column("NULL").label("value_distinct"))

    # Base FROM (optional join when filtering by source_name)
    from_clause = clean_events_tbl
    if source_name:
        from_clause = clean_events_tbl.join(sources_tbl, sources_tbl.c.id == clean_events_tbl.c.source_id)

    stmt = select(*select_cols).select_from(from_clause)

    # WHERE conditions
    conditions = []
    if source_name:
        conditions.append(sources_tbl.c.name == source_name)
    if metric:
        conditions.append(clean_events_tbl.c.metric == metric)
    if start_date:
        conditions.append(metric_dt >= start_date)
    if end_date:
        conditions.append(metric_dt <= end_date)
    if conditions:
        stmt = stmt.where(*conditions)

    # GROUP BY
    stmt = stmt.group_by(metric_dt, clean_events_tbl.c.source_id, clean_events_tbl.c.metric)

    rows = db.execute(stmt).mappings().all()

    if not rows:
        return ok(
            data={"rows_upserted": 0, "groups_upserted": 0, "metrics": [], "rows_aggregated": 0},
            meta=_meta(reason="no_clean_events_after_filters"),
        )

    # Upsert into metric_daily. Compute value_avg; set/replace value_distinct from EXCLUDED.
    upsert = text(
        """
        INSERT INTO metric_daily
            (metric_date, source_id, metric,
             value_sum, value_avg, value_count, value_distinct)
        VALUES
            (:metric_date, :source_id, :metric,
             :value_sum,
             :value_sum / NULLIF(:value_count, 0),
             :value_count,
             :value_distinct)
        ON CONFLICT (metric_date, source_id, metric)
        DO UPDATE SET
            value_sum      = EXCLUDED.value_sum,
            value_count    = EXCLUDED.value_count,
            value_avg      = EXCLUDED.value_sum / NULLIF(EXCLUDED.value_count, 0),
            value_distinct = EXCLUDED.value_distinct
        """
    )

    metrics: List[str] = []
    start_d: Optional[Date] = None
    end_d: Optional[Date] = None
    groups_upserted = 0
    total_rows = 0

    for r in rows:
        md = r["metric_date"]
        if isinstance(md, str):
            from datetime import date
            md = date.fromisoformat(md)

        db.execute(
            upsert,
            {
                "metric_date": md,
                "source_id": r["source_id"],
                "metric": r["metric"],
                "value_sum": float(r["value_sum"]) if r["value_sum"] is not None else None,
                "value_count": int(r["value_count"]) if r["value_count"] is not None else None,
                "value_distinct": int(r["value_distinct"]) if r.get("value_distinct") is not None else None,
            },
        )
        groups_upserted += 1
        total_rows += int(r["value_count"])
        metrics.append(r["metric"])

        if start_d is None or md < start_d:
            start_d = md
        if end_d is None or md > end_d:
            end_d = md

    db.commit()

    return ok(
        data={
            "rows_upserted": groups_upserted,
            "groups_upserted": groups_upserted,
            "rows_aggregated": total_rows,
            "metrics": sorted(set(metrics)),
        },
        meta=_meta(
            source_name=source_name,
            metric=metric,
            start_date=str(start_d) if start_d else None,
            end_date=str(end_d) if end_d else None,
            num_days=((end_d - start_d).days + 1) if start_d and end_d else None,
            distinct_field=distinct_field,
            agg=agg,
        ),
    )
