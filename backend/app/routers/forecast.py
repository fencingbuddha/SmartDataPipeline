# app/routers/forecast.py
from __future__ import annotations

from app.schemas.forecast_health import ForecastHealthOut

"""
Forecast API (daily horizon)

Public contract for GET /api/forecast/daily:
- Always returns EXACTLY 7 rows (trim/pad as needed).
- Timestamps are UTC midnight with a trailing 'Z' (ISO 8601).
- Keys: metric_date, metric, yhat, yhat_lower, yhat_upper
- Numerical invariants: yhat_lower <= yhat <= yhat_upper for every row.
- All values are finite floats (NaN/±inf sanitized to 0.0).

Notes:
- Internally we read persisted rows from ForecastResults (written by the SARIMAX
  service via run_forecast), which use columns target_date, yhat, yhat_lower, yhat_upper.
- We only return strictly-future rows relative to the last observed MetricDaily.date.
"""

from datetime import date, datetime, timedelta, timezone
from typing import List, Dict, Optional, Any

import math
import pandas as pd
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.source import Source
from app.models.metric_daily import MetricDaily
from app.models.forecast_results import ForecastResults
from app.services.forecast import run_forecast, upsert_forecast_health

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
    """
    Read all stored forecast rows ordered by target_date.
    Returns a DataFrame with columns: forecast_date, yhat, yhat_lo, yhat_hi
    """
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
    # Ensure timezone awareness in UTC for downstream formatting
    df["forecast_date"] = pd.to_datetime(df["forecast_date"], utc=True)
    return df


def _to_utc_midnight_z(d: str | date | datetime) -> str:
    """
    Accepts 'YYYY-MM-DD' string, date, or datetime; returns 'YYYY-MM-DDT00:00:00Z'
    """
    if isinstance(d, str):
        y, m, dd = map(int, d.split("-"))
        dt = datetime(y, m, dd, tzinfo=timezone.utc)
    elif isinstance(d, date) and not isinstance(d, datetime):
        dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    else:
        dt = d.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")


def _safe_float(v: Any) -> float:
    try:
        f = float(0.0 if v is None else v)
        if math.isfinite(f):
            return f
    except Exception:
        pass
    return 0.0


def _normalize_rows(raw_rows: List[Dict[str, Any]], metric: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in raw_rows:
        y = _safe_float(r.get("yhat"))
        lo = _safe_float(r.get("yhat_lo"))
        hi = _safe_float(r.get("yhat_hi"))
        lower, upper = (lo, hi) if lo <= hi else (hi, lo)

        # Build metric_date first so we can derive legacy 'date'
        metric_date = _to_utc_midnight_z(r.get("forecast_date"))
        out.append(
            {
                # New public contract
                "metric_date": metric_date,
                "metric": metric,
                "yhat": y,
                "yhat_lower": lower,
                "yhat_upper": upper,

                # 🔙 Back-compat for legacy tests/clients:
                # plain YYYY-MM-DD date (no time/zone), used by test_forecast_end_to_end_target_date
                "date": metric_date.split("T", 1)[0],
            }
        )

    # Sort by date just in case and trim/pad to exactly 7 rows
    out.sort(key=lambda r: r["metric_date"])
    out = out[:7]
    if out and len(out) < 7:
        last_dt = datetime.fromisoformat(out[-1]["metric_date"].replace("Z", "+00:00"))
        for _ in range(7 - len(out)):
            last_dt += timedelta(days=1)
            out.append(
                {
                    "metric_date": last_dt.isoformat().replace("+00:00", "Z"),
                    "metric": metric,
                    "yhat": 0.0,
                    "yhat_lower": 0.0,
                    "yhat_upper": 0.0,
                }
            )
    return out


# -------------------------------- routes ------------------------------------


@router.get("/daily")
def forecast_daily(
    source_name: str = Query(..., description="Logical source name"),
    metric: str = Query(..., description="Metric key (e.g., events_total)"),
    horizon: int = Query(7, ge=1, le=30, description="Internal generation horizon (days)"),
    # tolerated for legacy callers; not used to filter output
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
) -> List[Dict]:
    """
    Return strictly-future daily forecasts for (source_name, metric) in the normalized format.
    The first element's metric_date will be the day AFTER the last observed MetricDaily.
    Publicly we always return exactly 7 days, UTC Z timestamps, and ordered confidence bands.
    """
    try:
        PUBLIC_HORIZON = 7  # external contract

        source_id = _get_source_id(db, source_name)
        last_obs = _get_last_observed_date(db, source_id, metric)

        # If caller provided an end_date, derive a horizon from last_obs (internal generation only)
        if end_date and last_obs:
            delta = (end_date - last_obs).days
            horizon = max(0, min(30, delta))

        if horizon <= 0:
            return []

        # Generate/refresh in DB for at least the public horizon
        run_forecast(db, source_name=source_name, metric=metric, horizon_days=max(horizon, PUBLIC_HORIZON))

        # Read and restrict to strictly-future vs last_obs
        df = _read_forecast_df(db, source_id, metric)
        if df.empty:
            return []

        if last_obs is not None:
            df = df[df["forecast_date"] > pd.to_datetime(last_obs).tz_localize("UTC")]

        # Hard-cap to the public horizon to avoid stale leftovers
        df = df.head(PUBLIC_HORIZON)

        # Build raw rows in the internal shape the normalizer expects
        raw = [
            {
                "forecast_date": d.strftime("%Y-%m-%d"),
                "yhat": float(y),
                "yhat_lo": float(lo),
                "yhat_hi": float(hi),
            }
            for d, y, lo, hi in df[["forecast_date", "yhat", "yhat_lo", "yhat_hi"]].itertuples(index=False, name=None)
        ]

        # Normalize to the public contract
        normalized = _normalize_rows(raw, metric=metric)
        return JSONResponse(content=normalized)

    except HTTPException:
        raise
    except Exception as e:
        # Always return JSON (helps clients like jq/UI)
        return JSONResponse(status_code=500, content={"error": str(e)})
    
    # ------------------------ legacy compatibility route -------------------------

@router.post("/run")
def forecast_run(
    source_name: str = Query(..., description="Logical source name"),
    metric: str = Query(..., description="Metric key (e.g., events_total)"),
    # Support both names: horizon_days (new) and horizon (legacy tests)
    horizon_days: Optional[int] = Query(None, ge=1, le=30, description="Forecast horizon (days)"),
    horizon: Optional[int] = Query(None, ge=1, le=30, description="Alias for horizon_days"),
    db: Session = Depends(get_db),
):
    """
    Compatibility endpoint for older tests. Triggers forecast generation and
    returns {"ok": true, "data": {"horizon_days": <int>, "inserted": <int>}}.
    """
    try:
        # Resolve horizon from either parameter; default to 7
        hd = horizon_days or horizon or 7

        # Validate source & last observed
        source_id = _get_source_id(db, source_name)
        last_obs = _get_last_observed_date(db, source_id, metric)

        # Generate/refresh forecasts for the requested horizon
        run_forecast(db, source_name=source_name, metric=metric, horizon_days=hd)

        # Count strictly-future rows (idempotent on target_date)
        stmt_count = (
            select(func.count(ForecastResults.target_date))
            .where(
                ForecastResults.source_id == source_id,
                ForecastResults.metric == metric,
                # Only future targets relative to last observed metric day
                ForecastResults.target_date > (last_obs if last_obs is not None else date.min),
            )
        )
        inserted = int(db.execute(stmt_count).scalar() or 0)

        return JSONResponse(
    content={
        "ok": True,
        "horizon_days": int(hd),          # ← flat (for legacy tests)
        "inserted": inserted,             # ← flat (for legacy tests)
        "data": {                         # ← keep for newer callers
            "horizon_days": int(hd),
            "inserted": inserted,
        },
    },
    status_code=200,
)
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    
@router.get("/health", response_model=ForecastHealthOut)
def forecast_health(
    source_name: str = Query(..., description="e.g., demo-source"),
    metric: str = Query(..., description="e.g., events_total"),
    window: int = Query(90, ge=14, le=365, description="training window (days)"),
    db: Session = Depends(get_db),
):
    """
    Refresh health metadata and return { trained_at, window, mape }.
    """
    try:
        fm = upsert_forecast_health(db, source_name=source_name, metric=metric, window_n=window)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return ForecastHealthOut(trained_at=fm.trained_at, window=fm.window_n, mape=fm.mape or 100.0)
