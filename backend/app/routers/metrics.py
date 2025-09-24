from __future__ import annotations
from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.metrics import fetch_metric_daily
from app.models import source as models_source 

from sqlalchemy import text
from fastapi.responses import StreamingResponse
import io, csv

from statistics import mean, stdev
from math import isfinite

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

class MetricDailyOut(BaseModel):
    metric_date: date
    source_id: int
    metric: str
    # Full shape for UI tiles/table (optional so we stay tolerant)
    value_sum: Optional[float] = None
    value_avg: Optional[float] = None
    value_count: Optional[int] = None
    value_distinct: Optional[int] = None
    # Legacy/simplified single value (chart uses this)
    value: Optional[float] = None

    model_config = {"from_attributes": True}  # Pydantic v2

# APPEND to routers/metrics.py (below your /daily handler)
@router.get("/names")
def list_metric_names(
    source_name: str | None = Query(None),
    source_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    # resolve source_name -> source_id (reuse your pattern)
    if source_id is None and source_name:
        sid = db.query(models_source.Source.id)\
                .filter(models_source.Source.name == source_name)\
                .scalar()
        if sid is None:
            return []
        source_id = sid

    # fast and simple: SQL for distinct metric names in MetricDaily
    rows = db.execute(
        text("""
            SELECT DISTINCT metric
            FROM metric_daily
            WHERE (:sid IS NULL OR source_id = :sid)
            ORDER BY metric
        """),
        {"sid": source_id},
    )
    # rows.fetchall() gives tuples; use .scalars() if available
    try:
        return rows.scalars().all()
    except Exception:
        return [r[0] for r in rows.fetchall()]


@router.get("/daily", response_model=list[MetricDailyOut])
def get_metric_daily(
    # UI usually sends source_name; keep source_id for power users/tests
    source_name: str | None = Query(None),
    source_id: int | None = Query(None),
    metric: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    distinct_field: str | None = Query(None),  # passthrough if your service uses it
    agg: Literal["sum", "avg", "count"] = Query("sum"),
    limit: int = Query(1000, ge=1, le=10_000),
    db: Session = Depends(get_db),
):
    # Resolve source_name -> source_id if needed
    if source_id is None and source_name:
        sid = db.query(models_source.Source.id).filter(
            models_source.Source.name == source_name
        ).scalar()
        if sid is None:
            raise HTTPException(status_code=404, detail=f"Unknown source: {source_name}")
        source_id = sid

    rows = fetch_metric_daily(
        db,
        source_id=source_id,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        # if your service supports it, pass distinct_field here too
    )

    out: list[MetricDailyOut] = []
    for r in rows:
        # r should have .value_sum, .value_avg, .value_count, .value_distinct
        value_sum = getattr(r, "value_sum", None)
        value_avg = getattr(r, "value_avg", None)
        value_count = getattr(r, "value_count", None)
        value_distinct = getattr(r, "value_distinct", None)

        # Preserve your existing `agg` behavior for the single `value` field
        if agg == "avg" and value_avg is not None:
            single_value = float(value_avg)
        elif agg == "count" and value_count is not None:
            single_value = float(value_count)
        else:
            # default to sum; if missing, fall back to whatever you have
            single_value = (
                float(value_sum)
                if value_sum is not None
                else (
                    float(value_avg)
                    if value_avg is not None
                    else (float(value_count) if value_count is not None else None)
                )
            )

        out.append(
            MetricDailyOut(
                metric_date=r.metric_date,
                source_id=r.source_id,
                metric=r.metric,
                value_sum=value_sum,
                value_avg=value_avg,
                value_count=value_count,
                value_distinct=value_distinct,
                value=single_value,
            )
        )
    return out

@router.get("/export/csv")
def export_metrics_csv(
    source_name: str | None = Query(None),
    source_id: int | None = Query(None),
    metric: str = Query(...),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db: Session = Depends(get_db),
):
    # resolve source_name -> id
    if source_id is None and source_name:
        sid = db.query(models_source.Source.id)\
                .filter(models_source.Source.name == source_name)\
                .scalar()
        if sid is None:
            return []
        source_id = sid

    rows = fetch_metric_daily(
        db,
        source_id=source_id,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        limit=10_000,
    )

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["metric_date","source_id","metric","value_sum","value_avg","value_count","value_distinct","value"])
    for r in rows:
        w.writerow([
            r.metric_date,
            r.source_id,
            r.metric,
            getattr(r, "value_sum", None),
            getattr(r, "value_avg", None),
            getattr(r, "value_count", None),
            getattr(r, "value_distinct", None),
            # keep 'value' for the chart fallback
            getattr(r, "value", getattr(r, "value_sum", None)),
        ])

    headers = {"Content-Disposition": 'attachment; filename="metric_daily.csv"'}
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers=headers,
    )


@router.get("/anomaly/rolling")
def rolling_anomaly(
    source_name: str | None = Query(None),
    source_id: int | None = Query(None),
    metric: str = Query(...),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    window: int = Query(7, ge=2, le=60),         # lookback window (days)
    z_thresh: float = Query(3.0, ge=0.5, le=10), # anomaly threshold |z|>= z_thresh
    db: Session = Depends(get_db),
):
    # 1) Resolve source_name -> id (reuse your pattern)
    if source_id is None and source_name:
        sid = db.query(models_source.Source.id)\
                .filter(models_source.Source.name == source_name)\
                .scalar()
        if sid is None:
            raise HTTPException(status_code=404, detail=f"Unknown source: {source_name}")
        source_id = sid

    # 2) Fetch daily rows ordered by date
    rows = fetch_metric_daily(
        db,
        source_id=source_id,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        limit=10_000,
    )

    # 3) Build (date, value) series (prefer value_sum; fallback to value)
    series: list[tuple[date, int, str, float]] = []
    for r in rows:
        v = getattr(r, "value_sum", None)
        if v is None:
            v = getattr(r, "value", None)
        if v is None:
            continue
        series.append((r.metric_date, r.source_id, r.metric, float(v)))

    # 4) Rolling z-score using *previous* window (no leakage)
    out = []
    for i, (d, sid, m, v) in enumerate(series):
        prev_vals = [vv for (_, _, _, vv) in series[max(0, i - window): i]]
        # need enough history to compute std
        if len(prev_vals) < max(3, min(window - 1, window)):
            out.append({"metric_date": d, "source_id": sid, "metric": m, "value": v, "z": None, "is_anomaly": False})
            continue
        mu = mean(prev_vals)
        sd = stdev(prev_vals)
        z = 0.0 if sd == 0 else (v - mu) / sd
        is_anom = abs(z) >= z_thresh and isfinite(z)
        out.append({"metric_date": d, "source_id": sid, "metric": m, "value": v, "z": z, "is_anomaly": is_anom})

    return out

