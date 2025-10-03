from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Dict, Any

from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class MetricDailyRow:
    metric_date: str
    source_id: int
    metric: str
    value_sum: Optional[float]
    value_avg: Optional[float]
    value_count: Optional[float]
    value_distinct: Optional[float]
    value: Optional[float]


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _row_value(value: Any, value_sum: Any, value_avg: Any, value_count: Any) -> Optional[float]:
    """Preferred value: value -> value_sum -> value_avg -> value_count."""
    for cand in (value, value_sum, value_avg, value_count):
        f = _to_float(cand)
        if f is not None:
            return f
    return None


def _has_column(db: Session, table_name: str, column_name: str, schema: str = "public") -> bool:
    """Return True if (schema.table_name).column_name exists."""
    q = text(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = :schema
          AND table_name   = :table
          AND column_name  = :column
        LIMIT 1
        """
    )
    return db.execute(q, {"schema": schema, "table": table_name, "column": column_name}).first() is not None


def fetch_metric_daily(
    db: Session,
    *,
    source_id: Optional[int] = None,
    source_name: Optional[str] = None,
    metric: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 1000,
    distinct_field: Optional[str] = None,
    agg: Optional[str] = None,
) -> List[MetricDailyRow]:
    """
    Fetch rows from metric_daily with optional filters (inclusive dates).
    Returns a list of MetricDailyRow with attribute-style access.
    """
    joins: List[str] = []
    where = ["1=1"]
    params: Dict[str, object] = {"limit": int(limit)}

    if source_id is not None:
        where.append("md.source_id = :source_id")
        params["source_id"] = source_id
    elif source_name:
        joins.append("JOIN sources s ON s.id = md.source_id")
        where.append("s.name = :source_name")
        params["source_name"] = source_name

    if metric:
        where.append("md.metric = :metric")
        params["metric"] = metric
    if start_date:
        where.append("md.metric_date >= :start_date")
        params["start_date"] = start_date
    if end_date:
        where.append("md.metric_date <= :end_date")
        params["end_date"] = end_date

    # Build SELECT list. If md.value column doesn't exist, select a typed NULL so the key is always present.
    select_cols = """
            md.metric_date::date        AS d,
            md.source_id                AS source_id,
            md.metric                   AS metric,
            md.value_sum                AS value_sum,
            md.value_avg                AS value_avg,
            md.value_count              AS value_count,
            md.value_distinct           AS value_distinct
    """.strip()

    if _has_column(db, "metric_daily", "value"):
        select_cols += ", md.value AS value"
    else:
        select_cols += ", NULL::double precision AS value"

    sql = f"""
        SELECT
            {select_cols}
        FROM metric_daily md
        {' '.join(joins)}
        WHERE {' AND '.join(where)}
        ORDER BY d, md.source_id, md.metric
        LIMIT :limit
    """

    rows = db.execute(text(sql), params).mappings().all()

    out: List[MetricDailyRow] = []
    for r in rows:
        d = r["d"]
        # Build final "value" fallback
        final_value = _row_value(
            r.get("value"),
            r.get("value_sum"),
            r.get("value_avg"),
            r.get("value_count"),
        )
        out.append(
            MetricDailyRow(
                metric_date=d.isoformat() if hasattr(d, "isoformat") else str(d),
                source_id=int(r["source_id"]),
                metric=str(r["metric"]),
                value_sum=_to_float(r.get("value_sum")),
                value_avg=_to_float(r.get("value_avg")),
                value_count=_to_float(r.get("value_count")),
                value_distinct=_to_float(r.get("value_distinct")),
                value=final_value,
            )
        )
    return out


def fetch_metric_daily_as_dicts(
    db: Session,
    *,
    source_id: Optional[int] = None,
    source_name: Optional[str] = None,
    metric: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 1000,
) -> List[Dict[str, Any]]:
    """
    Compact dicts with expected keys: metric_date, source_id, metric, value.
    """
    rows = fetch_metric_daily(
        db,
        source_id=source_id,
        source_name=source_name,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "metric_date": r.metric_date,
                "source_id": r.source_id,
                "metric": r.metric,
                "value": r.value,
                # keep extras
                "value_sum": r.value_sum,
                "value_avg": r.value_avg,
                "value_count": r.value_count,
                "value_distinct": r.value_distinct,
            }
        )
    return out


def fetch_metric_names(
    db: Session,
    *,
    source_name: Optional[str] = None,
) -> List[str]:
    """
    Distinct metric names, optionally scoped by source_name.
    """
    if source_name:
        return (
            db.execute(
                text(
                    """
                    SELECT DISTINCT md.metric
                    FROM metric_daily md
                    JOIN sources s ON s.id = md.source_id
                    WHERE s.name = :source_name
                    ORDER BY md.metric
                    """
                ),
                {"source_name": source_name},
            )
            .scalars()
            .all()
        )
    return db.execute(text("SELECT DISTINCT metric FROM metric_daily ORDER BY metric")).scalars().all()


def rolling_anomalies(
    db: Session,
    *,
    source_id: Optional[int] = None,
    source_name: Optional[str] = None,
    metric: str,
    start_date: date,
    end_date: date,
    window: int = 3,
    z_threshold: float = 2.0,
) -> List[Dict[str, Any]]:
    """
    Reference implementation available for use if you switch the router to call this.
    (Your current router-side implementation is fine once rows have attribute access.)
    """
    # Use the dict version
    series = fetch_metric_daily_as_dicts(
        db,
        source_id=source_id,
        source_name=source_name,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        limit=10_000,
    )

    # Simple rolling z-score of previous `window` points
    vals: List[float] = []
    out: List[Dict[str, Any]] = []
    from statistics import mean, pstdev

    for row in series:
        v = row["value"]
        mu = None
        sd = None
        is_outlier = False
        if len(vals) >= window:
            last = vals[-window:]
            mu = mean(last)
            sd = pstdev(last) if len(set(last)) > 1 else 0.0
            if sd and v is not None and abs(v - mu) >= z_threshold * sd:
                is_outlier = True
        out.append(
            {
                "date": row["metric_date"],
                "value": v,
                "rolling_mean": mu,
                "rolling_std": sd,
                "is_outlier": is_outlier,
            }
        )
        if v is not None:
            vals.append(v)
    return out
