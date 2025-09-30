from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.anomaly import detect_anomalies, SeriesPoint, AnomalyPoint

router = APIRouter(prefix="/api/metrics/anomaly", tags=["anomaly", "metrics"])


class AnomalyPointOut(BaseModel):
    metric_date: date
    value: float
    z: float


class SeriesPointOut(BaseModel):
    metric_date: date
    value: Optional[float] = Field(None, description="Selected value_* after fallback (may be null).")


class RollingAnomalyResponse(BaseModel):
    points: List[SeriesPointOut] = Field(default_factory=list, description="Full series for the selected metric.")
    anomalies: List[AnomalyPointOut] = Field(default_factory=list, description="Subset of points flagged as anomalies.")
    window: int
    z_thresh: float
    source_name: str
    metric: str


@router.get(
    "/rolling",
    response_model=RollingAnomalyResponse,
    summary="Detect anomalies via rolling z-score (no look-ahead leakage).",
)
def rolling_anomaly_endpoint(
    *,
    db: Session = Depends(get_db),
    source_name: str = Query(..., description="Logical data source name (e.g., 'demo-source')."),
    metric: str = Query(..., description="Metric key (e.g., 'events_total')."),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    window: int = Query(7, ge=2, le=365, description="Size of the prior window used for mean/stddev."),
    z_thresh: float = Query(3.0, gt=0, le=20, description="Absolute z-score threshold to flag anomalies."),
    value_field: Optional[str] = Query(
        None,
        description="Optional value_* column to use (value_sum|value_avg|value_count|value_distinct). Falls back if missing.",
    ),
):
    """
    Computes rolling z-scores using the *previous* N observations only and flags
    outliers where |z| >= z_thresh. Early points (< window) return no z-score.
    """
    try:
        points, anomalies = detect_anomalies(
            db,
            source_name=source_name,
            metric=metric,
            start_date=start_date,
            end_date=end_date,
            window=window,
            z_thresh=z_thresh,
            value_field=value_field,
        )
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly detection failed: {type(ex).__name__}",
        )

    # If source not found or no rows, we still return a 200 with empty arrays for a graceful UI experience
    out = RollingAnomalyResponse(
        points=[SeriesPointOut(metric_date=p.metric_date, value=p.value) for p in points],
        anomalies=[AnomalyPointOut(metric_date=a.metric_date, value=a.value, z=a.z) for a in anomalies],
        window=window,
        z_thresh=z_thresh,
        source_name=source_name,
        metric=metric,
    )
    return out
