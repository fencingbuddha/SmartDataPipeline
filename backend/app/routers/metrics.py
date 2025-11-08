# app/routers/metrics.py
from __future__ import annotations

from datetime import date
import math
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, join

from app.db.session import get_db
from app.models.source import Source
from app.models.metric_daily import MetricDaily

# Service layer (used where helpful)
from app.services.metrics_fetch import (
    fetch_metric_daily as _fetch_metric_daily,
    fetch_metric_names as _fetch_metric_names,
)
from app.services.metrics_calc import normalize_metric_rows, to_csv as build_metrics_csv

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


# ---------------------------------------------------------------------------
# /api/metrics/names  -> enveloped list[str]
# ---------------------------------------------------------------------------
@router.get("/names")
def list_metric_names(
    source_name: Optional[str] = Query(
        default=None, description="Optional filter to limit metric names to a specific source"
    ),
    db: Session = Depends(get_db),
) -> dict:
    try:
        names = _fetch_metric_names(db, source_name=source_name) or []
        return {
            "ok": True,
            "data": names,  # list[str]
            "error": None,
            "meta": {
                "source_name": source_name,
                "count": len(names),
            },
        }
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Failed to fetch metric names: {ex}") from ex


# ---------------------------------------------------------------------------
# /api/metrics/daily  -> enveloped list[dict]
# ---------------------------------------------------------------------------
@router.get("/daily")
def get_metrics_daily(
    source_id: Optional[int] = Query(None, description="Numeric source ID"),
    source_name: Optional[str] = Query(None, description="Source name (alternative to source_id)"),
    metric: str = Query(..., description="e.g., events_total"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    agg: Optional[str] = Query(
        None,
        description="Optional aggregation for unified 'value' field: one of ['sum','avg','count']",
    ),
    limit: Optional[int] = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """
    Enveloped daily metrics. Accepts either source_id OR source_name.
    If `agg` is provided, the unified `value` field is set to:
      - 'sum'   -> value_sum  (default if not provided)
      - 'avg'   -> value_avg
      - 'count' -> value_count
    """
    # Require at least one of source_id/source_name
    if source_id is None and not source_name:
        raise HTTPException(status_code=422, detail="Provide either source_id or source_name")

    try:
        rows = _fetch_metric_daily(
            db,
            source_id=source_id,
            source_name=source_name,
            metric=metric,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        ) or []

        agg_norm = (agg or "sum").lower()
        if agg and agg_norm not in ("sum", "avg", "count"):
            raise HTTPException(status_code=400, detail=f"Unsupported agg '{agg}'. Use one of: sum, avg, count")

        out_rows = normalize_metric_rows(rows, agg=agg_norm)

        return {
            "ok": True,
            "data": out_rows,
            "error": None,
            "meta": {
                "source_id": source_id,
                "source_name": source_name,
                "metric": metric,
                "params": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None,
                    "agg": agg_norm,
                    "limit": limit,
                },
            },
        }
    except HTTPException:
        raise
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Failed to fetch daily metrics: {ex}") from ex



# ---------------------------------------------------------------------------
# /api/metrics/export/csv  -> required header columns
# ---------------------------------------------------------------------------
@router.get("/export/csv", response_class=Response)
def export_metrics_csv(
    source_name: str = Query(...),
    metric: str = Query(...),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
) -> Response:
    """
    CSV export with header containing at least:
      metric_date, source_id, metric, value, value_count, value_sum, value_avg
    'value' mirrors value_sum for compatibility with tests.
    """
    try:
        rows = _fetch_metric_daily(
            db,
            source_name=source_name,
            metric=metric,
            start_date=start_date,
            end_date=end_date,
            order="asc",
        )
        csv_text = build_metrics_csv(rows)
        return Response(
            content=csv_text,
            status_code=status.HTTP_200_OK,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{metric}_{source_name}.csv"'},
        )
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Failed to export CSV: {ex}") from ex


# ---------------------------------------------------------------------------
# /api/metrics/anomaly/rolling  -> points + anomalies (finite z)
# ---------------------------------------------------------------------------
@router.get("/anomaly/rolling")
def anomaly_rolling_inline(
    source_name: str = Query(...),
    metric: str = Query(...),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    window: int = Query(7, ge=2, le=365),
    z_thresh: float = Query(3.0, gt=0),
    value_field: str | None = Query("value_sum"),
    db: Session = Depends(get_db),
):
    """
    Rolling z-score using previous-only window; JSON-safe (no NaN/Inf in output).
    Returns: {"points":[...], "anomalies":[...]} where anomalies have "metric_date" and finite "z".
    """
    try:
        j = join(MetricDaily, Source, MetricDaily.source_id == Source.id)
        conds = [Source.name == source_name, MetricDaily.metric == metric]
        if start_date:
            conds.append(MetricDaily.metric_date >= start_date)
        if end_date:
            conds.append(MetricDaily.metric_date <= end_date)

        q = (
            select(
                MetricDaily.metric_date,
                MetricDaily.value_sum,
                MetricDaily.value_avg,
                MetricDaily.value_count,
                MetricDaily.value_distinct,
            )
            .select_from(j)
            .where(and_(*conds))
            .order_by(MetricDaily.metric_date.asc())
        )
        rows = db.execute(q).all()

        field = (value_field or "value_sum")
        series = []
        for r in rows:
            raw = getattr(r, field, None)
            val = float(raw) if raw is not None else None
            series.append({"metric_date": r.metric_date, "value": val})

        points: list[dict] = []
        anomalies: list[dict] = []
        zt = float(z_thresh)
        Z_CLAMP = 1e9  # large finite sentinel for flat-window spikes

        def _clamp_finite(x: float | None) -> float | None:
            if x is None:
                return None
            if not math.isfinite(x):
                return Z_CLAMP if x > 0 else -Z_CLAMP
            return x

        for i in range(len(series)):
            md = series[i]["metric_date"]
            iso = md.isoformat()
            v = series[i]["value"]

            point = {
                "metric_date": iso,
                "date": iso,
                "value": v,
                "z": None,
                "is_outlier": False,
            }

            if v is None:
                points.append(point)
                continue

            # Previous-only window [i - window, i)
            w0 = max(0, i - window)
            prev_vals = [s["value"] for s in series[w0:i] if s["value"] is not None]

            if len(prev_vals) < 2:
                points.append(point)
                continue

            mean = sum(prev_vals) / len(prev_vals)
            var = sum((x - mean) ** 2 for x in prev_vals) / (len(prev_vals) - 1)
            std = math.sqrt(var) if var > 0 else 0.0

            if std == 0.0:
                is_outlier = (v != mean)
                z = Z_CLAMP if is_outlier else 0.0
            else:
                z = (v - mean) / std
                is_outlier = abs(z) >= zt

            z = _clamp_finite(z)
            point["z"] = z
            point["is_outlier"] = is_outlier
            points.append(point)

            if is_outlier:
                anomalies.append({"metric_date": iso, "z": z})

        return {"points": points, "anomalies": anomalies}

    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Anomaly failure: {ex}") from ex
    
@router.get("/anomaly/iforest")
def anomaly_iforest_overlay(
    source_name: str = Query(...),
    metric: str = Query(...),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
):
    """
    Placeholder endpoint to satisfy UAT contract for anomaly overlay using Isolation Forest.
    Returns 204 No Content by design for now.
    """
    return Response(status_code=status.HTTP_204_NO_CONTENT)
