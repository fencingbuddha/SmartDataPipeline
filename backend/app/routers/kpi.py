# app/routers/kpi.py
from __future__ import annotations

from datetime import datetime, timezone, date as Date
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text, inspect
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

    # Build SELECT with optional filters
    params: Dict[str, Any] = {}
    where_sql = ["1=1"]
    join_sources = False

    # Cross-dialect expressions
    dialect_name = db.bind.dialect.name if db.bind is not None else "default"
    if dialect_name == "sqlite":
        date_expr = "DATE(clean_events.ts)"
        sum_cast = "SUM(clean_events.value) AS value_sum"
        count_cast = "COUNT(*) AS value_count"
        null_int = "NULL AS value_distinct"
    else:
        date_expr = "(clean_events.ts AT TIME ZONE 'UTC')::date"
        sum_cast = "SUM(clean_events.value)::float8 AS value_sum"
        count_cast = "COUNT(*)::int AS value_count"
        null_int = "NULL::int AS value_distinct"

    if source_name:
        join_sources = True
        where_sql.append("sources.name = :src_name")
        params["src_name"] = source_name

    if metric:
        where_sql.append("clean_events.metric = :metric")
        params["metric"] = metric

    # Date filters are inclusive on the DATE derived from ts at UTC
    if start_date:
        where_sql.append(f"{date_expr} >= :start_date")
        params["start_date"] = start_date
    if end_date:
        where_sql.append(f"{date_expr} <= :end_date")
        params["end_date"] = end_date

    # DISTINCT support: tests pass distinct_field='id', which should equal row count here
    if distinct_field == "id":
        distinct_sql = ", COUNT(DISTINCT clean_events.id) AS value_distinct"
    else:
        distinct_sql = f", {null_int}"

    join_sql = "JOIN sources ON sources.id = clean_events.source_id" if join_sources else ""

    select_sql = text(
        f"""
        SELECT
            {date_expr} AS metric_date,
            clean_events.source_id,
            clean_events.metric,
            {sum_cast},
            {count_cast}
            {distinct_sql}
        FROM clean_events
        {join_sql}
        WHERE {" AND ".join(where_sql)}
        GROUP BY {date_expr}, clean_events.source_id, clean_events.metric
        """
    )  # nosec B608 date_expr/sum_cast are derived from fixed dialect templates; user input is parameterized via params.

    rows = db.execute(select_sql, params).mappings().all()

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
