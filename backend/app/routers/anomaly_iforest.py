from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Iterable, List

import pandas as pd
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from app.services.anomaly_iforest import detect_iforest, IFParams

router = APIRouter(prefix="/api/metrics/anomaly", tags=["metrics-anomaly"])


class IFPoint(BaseModel):
    metric_date: date
    value: float
    score: float
    is_outlier: bool


class IFResponse(BaseModel):
    points: List[IFPoint]


@router.get("/iforest", response_model=IFResponse)
def anomaly_iforest(
    source_name: str,
    metric: str,
    start_date: date,
    end_date: date,
    contamination: float = Query(0.05, ge=0.001, le=0.5),
    n_estimators: int = Query(100, ge=10, le=1000),
):
    """
    Isolation Forest anomaly detection over MetricDaily time series.

    This endpoint intentionally does a lazy import of the data-fetch helper so the
    router can be imported even if the helper isn't implemented yet. Tests can
    monkeypatch `app.services.metrics.fetch_metric_daily_as_df` safely.
    """

    from app.services import metrics as metrics_service 

    fetch_metric_daily_as_df = getattr(metrics_service, "fetch_metric_daily_as_df", None)
    if fetch_metric_daily_as_df is None:
        raise HTTPException(
            status_code=500,
            detail="fetch_metric_daily_as_df not implemented in app.services.metrics",
        )

    # Fetch series as a DataFrame with at least ['metric_date','value']
    df: Optional[pd.DataFrame] = fetch_metric_daily_as_df(
        source_name=source_name,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        fields=("metric_date", "value"),
    )

    if df is None:
        # Unknown source or metric
        raise HTTPException(status_code=404, detail="Unknown source_name or metric")

    if df.empty:
        return IFResponse(points=[])

    # Ensure proper dtypes & ordering
    df = df.copy()
    df["metric_date"] = pd.to_datetime(df["metric_date"])
    df = df.sort_values("metric_date")

    # Run Isolation Forest
    out = detect_iforest(
        df,
        IFParams(contamination=contamination, n_estimators=n_estimators, random_state=42),
    )

    # Build response
    points: List[IFPoint] = []
    for row in out.itertuples(index=False):
        md = getattr(row, "metric_date")
        if isinstance(md, pd.Timestamp):
            md = md.date()
        elif isinstance(md, datetime):
            md = md.date()

        points.append(
            IFPoint(
                metric_date=md,
                value=float(getattr(row, "value")),
                score=float(getattr(row, "score")),
                is_outlier=bool(getattr(row, "is_outlier")),
            )
        )

    return IFResponse(points=points)
