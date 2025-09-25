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

from app.services.metrics import rolling_anomalies

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
            return []
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
    window: int = Query(7, ge=2, le=60),
    z_thresh: float = Query(3.0, ge=0.5, le=10),
    db: Session = Depends(get_db),
):
    # Resolve source_name -> id
    if source_id is None and source_name:
        sid = db.query(models_source.Source.id)\
                .filter(models_source.Source.name == source_name)\
                .scalar()
        if sid is None:
            raise HTTPException(status_code=404, detail=f"Unknown source: {source_name}")
        source_id = sid

    # Pull daily rows
    rows = fetch_metric_daily(
        db,
        source_id=source_id,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        limit=10_000,
    )

    # Rolling z-score using previous `window` points only
    from statistics import mean, pstdev

    history: list[float] = []
    out: list[dict] = []

    def val_of(r) -> float | None:
        # prefer .value, then .value_sum, then .value_avg, then .value_count
        for k in ("value", "value_sum", "value_avg", "value_count"):
            v = getattr(r, k, None)
            if v is not None:
                return float(v)
        return None

    for r in rows:
        v = val_of(r)
        mu = None
        sd = None
        is_outlier = False

        if len(history) >= window:
            last = history[-window:]
            mu = mean(last)
            sd = pstdev(last)  # population stdev; 0.0 if last are identical

            if v is not None:
                if sd == 0:
                    # Fallback: with a flat window, any non-equal value is anomalous
                    is_outlier = (v != mu)
                else:
                    is_outlier = abs(v - mu) >= z_thresh * sd

        out.append({
            "date": r.metric_date,
            "value": v,
            "rolling_mean": mu,
            "rolling_std": sd,
            "is_outlier": is_outlier,
        })

        if v is not None:
            history.append(v)

    return out

@router.get("/metrics/anomaly/rolling")
def rolling_anomaly_endpoint(
    source_name: str = Query(...),
    metric: str = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    window: int = Query(3, ge=2, le=30),
    db: Session = Depends(get_db),
):
    return rolling_anomalies(
        db,
        source_name=source_name,
        metric=metric,
        start=start_date,
        end=end_date,
        window=window,
        z_threshold=3.0,
    )