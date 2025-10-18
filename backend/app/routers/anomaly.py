# app/routers/anomaly.py
from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["anomaly"])


def _delegate_to_metrics(
    *,
    source_name: str,
    metric: str,
    start_date: date | None,
    end_date: date | None,
    window: int,
    z_thresh: float,
    value_field: str | None,
    db: Session,
):
    """
    Delegates to the metrics inline implementation to keep a single source of truth.
    Import is inside the function to avoid circular imports at module load time.
    """
    try:
        from app.routers.metrics import anomaly_rolling_inline
        return anomaly_rolling_inline(
            source_name=source_name,
            metric=metric,
            start_date=start_date,
            end_date=end_date,
            window=window,
            z_thresh=z_thresh,
            value_field=value_field,
            db=db,
        )
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Anomaly failure: {ex}") from ex


@router.get("/api/anomaly/rolling")
def rolling_anomaly(
    source_name: str = Query(...),
    metric: str = Query(...),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    window: int = Query(7, ge=2, le=365),
    z_thresh: float = Query(3.0, gt=0),
    value_field: str | None = Query("value_sum"),
    db: Session = Depends(get_db),
):
    return _delegate_to_metrics(
        source_name=source_name,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        window=window,
        z_thresh=z_thresh,
        value_field=value_field,
        db=db,
    )


@router.get("/api/metrics/anomaly/rolling")
def rolling_anomaly_compat(
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
    Compatibility path so tests that include only the anomaly router can call
    /api/metrics/anomaly/rolling directly.
    """
    return _delegate_to_metrics(
        source_name=source_name,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        window=window,
        z_thresh=z_thresh,
        value_field=value_field,
        db=db,
    )
