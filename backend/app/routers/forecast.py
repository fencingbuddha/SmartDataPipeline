# app/routers/forecast.py
from __future__ import annotations

"""
Forecast API (daily horizon)
- Generates/reads strictly-future forecasts for a (source_name, metric).
- Horizon is controlled by `horizon` (preferred). If `end_date` is supplied,
  horizon is derived as (end_date - last_observed_date).
- Output is NOT filtered by start/end; those are training/window concerns only.
- Payload is normalized for the UI: forecast_date, yhat, yhat_lo, yhat_hi.
"""

from datetime import date
from typing import List, Dict, Optional

import pandas as pd
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.source import Source
from app.models.metric_daily import MetricDaily
from app.models.forecast_results import ForecastResults
from app.services.forecast import run_forecast

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


# ------------------------------- helpers ------------------------------------


def _get_source_id(db: Session, source_name: str) -> int:
    sid = db.query(Source.id).filter_by(name=source_name).scalar()
    if sid is None:
        raise HTTPException(status_code=404, detail=f"Unknown source '{source_name}'")
    return int(sid)


def _get_last_observed_date(db: Session, source_id: int, metric: str) -> Optional[date]:
    stmt = (
        select(func.max(MetricDaily.metric_date))
        .where(MetricDaily.source_id == source_id, MetricDaily.metric == metric)
    )
    return db.execute(stmt).scalar()  # -> date | None


def _read_forecast_df(db: Session, source_id: int, metric: str) -> pd.DataFrame:
    stmt = (
        select(
            ForecastResults.target_date,
            ForecastResults.yhat,
            ForecastResults.yhat_lower,
            ForecastResults.yhat_upper,
        )
        .where(ForecastResults.source_id == source_id, ForecastResults.metric == metric)
        .order_by(ForecastResults.target_date.asc())
    )
    rows = db.execute(stmt).all()
    if not rows:
        return pd.DataFrame(columns=["forecast_date", "yhat", "yhat_lo", "yhat_hi"])
    df = pd.DataFrame(rows, columns=["forecast_date", "yhat", "yhat_lo", "yhat_hi"])
    df["forecast_date"] = pd.to_datetime(df["forecast_date"])
    return df


# -------------------------------- routes ------------------------------------


@router.get("/daily")
def forecast_daily(
    source_name: str = Query(..., description="Logical source name"),
    metric: str = Query(..., description="Metric key (e.g., events_total)"),
    horizon: int = Query(7, ge=1, le=30, description="Forecast horizon in days"),
    # tolerated for legacy callers; not used to filter output
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
) -> List[Dict]:
    """
    Return strictly-future daily forecasts for (source_name, metric).
    The first element's forecast_date will be the day AFTER the last observed MetricDaily.
    """
    try:
        source_id = _get_source_id(db, source_name)
        last_obs = _get_last_observed_date(db, source_id, metric)

        # If caller provided an end_date, derive a horizon from last_obs.
        if end_date and last_obs:
            delta = (end_date - last_obs).days
            # clamp to [0, 30]; 0 means "no future within requested window"
            horizon = max(0, min(30, delta))

        if horizon <= 0:
            return []  # empty future window is not an error

        # Generate / refresh horizon in DB (service enforces strictly-future indexing)
        run_forecast(db, source_name=source_name, metric=metric, horizon_days=horizon)

        # Read all forecast rows and filter to strictly-future vs last_obs
        df = _read_forecast_df(db, source_id, metric)
        if df.empty:
            return []

        if last_obs:
            df = df[df["forecast_date"] > pd.to_datetime(last_obs)]

        # Hard-cap to requested horizon to avoid stale leftovers
        if horizon:
            df = df.head(horizon)

        out = [
            {
                "forecast_date": d.strftime("%Y-%m-%d"),
                "metric": metric,
                "yhat": float(y),
                "yhat_lo": float(lo),
                "yhat_hi": float(hi),
            }
            for d, y, lo, hi in df[["forecast_date", "yhat", "yhat_lo", "yhat_hi"]].itertuples(index=False, name=None)
        ]
        return JSONResponse(content=out)
    except HTTPException:
        raise
    except Exception as e:
        # Always return JSON (helps clients like jq/UI)
        return JSONResponse(status_code=500, content={"error": str(e)})
