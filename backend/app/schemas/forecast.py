from __future__ import annotations
from typing import List, Optional
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import ok, fail, ResponseMeta
from app.services.metrics_fetch import fetch_metric_daily
from app.models import source as models_source

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


def _meta(**params) -> ResponseMeta:
    clean = {k: v for k, v in params.items() if v is not None}
    return ResponseMeta(
        params=clean or None,
        generated_at=datetime.now(timezone.utc).isoformat()
    )


def _resolve_source_id(db: Session, source_id: Optional[int], source_name: Optional[str]) -> Optional[int]:
    if source_id is not None:
        return source_id
    if source_name:
        sid = db.query(models_source.Source.id)\
                .filter(models_source.Source.name == source_name)\
                .scalar()
        return sid
    return None


@router.get("")
def forecast(
    source_name: str | None = Query(None, description="Logical dataset/source name"),
    source_id: int | None = Query(None, description="Numeric source id (optional)"),
    metric: str = Query(..., description="Metric to forecast (e.g., events_total)"),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    horizon: int = Query(14, ge=1, le=90, description="Days to forecast"),
    ci: int = Query(90, ge=50, le=99, description="Confidence interval percent"),
    db: Session = Depends(get_db),
):
    """
    Returns { points: [{date, forecast, lower, upper}] } for the next `horizon` days.
    Tries SARIMAX if statsmodels is available; otherwise uses a simple moving-average
    baseline with empirical residual variance.
    """
    sid = _resolve_source_id(db, source_id, source_name)
    if source_name and sid is None:
        return fail(code="UNKNOWN_SOURCE", message=f"Unknown source: {source_name}", status_code=404, meta=_meta(source_name=source_name))

    rows = fetch_metric_daily(
        db,
        source_id=sid,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        limit=10_000,
    )

    # Build ordered historical series
    hist_dates: List[date] = []
    hist_vals: List[float] = []

    def val_of(r) -> float | None:
        for k in ("value", "value_sum", "value_avg", "value_count"):
            v = getattr(r, k, None)
            if v is not None:
                return float(v)
        return None

    for r in rows:
        v = val_of(r)
        if v is not None:
            hist_dates.append(r.metric_date)
            hist_vals.append(v)

    if len(hist_vals) < 7:
        # Not enough data to fit a decent model; return flatline using last known value
        last_date = hist_dates[-1] if hist_dates else (end_date or date.today())
        last_val = hist_vals[-1] if hist_vals else 0.0
        pts = []
        for i in range(1, horizon + 1):
            d = last_date + timedelta(days=i)
            pts.append({"date": d, "forecast": float(last_val), "lower": float(last_val), "upper": float(last_val)})
        return ok(
            data={"points": pts},
            meta=_meta(
                source_id=sid, source_name=source_name, metric=metric,
                start_date=str(start_date) if start_date else None,
                end_date=str(end_date) if end_date else None,
                method="naive_hold_last", horizon=horizon, confidence=ci, reason="insufficient_history"
            ),
        )

    # Try SARIMAX first; if unavailable, fall back to moving-average extrapolation
    points: List[dict] = []
    method_used = "sarimax"
    try:
        import numpy as np
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        y = np.array(hist_vals, dtype=float)
        # A lightweight SARIMAX config; adjust if you have a tuned spec.
        model = SARIMAX(y, order=(1, 1, 1), seasonal_order=(0, 1, 1, 7), trend="n", enforce_stationarity=False, enforce_invertibility=False)
        fit = model.fit(disp=False)

        alpha = 1 - (ci / 100.0)
        fc = fit.get_forecast(steps=horizon)
        mean = fc.predicted_mean
        conf = fc.conf_int(alpha=alpha)
        last_date = hist_dates[-1]

        for i in range(horizon):
            d = last_date + timedelta(days=i + 1)
            lower = float(conf[i, 0])
            upper = float(conf[i, 1])
            points.append({"date": d, "forecast": float(mean[i]), "lower": lower, "upper": upper})
    except Exception:
        # Moving-average + empirical residual variance fallback
        method_used = "moving_average"
        window = min(14, len(hist_vals))
        ma = sum(hist_vals[-window:]) / float(window)

        # Residuals vs. moving average for a crude CI
        residuals = [v - ma for v in hist_vals[-window:]]
        if len(residuals) > 1:
            import math
            var = sum((e ** 2 for e in residuals)) / (len(residuals) - 1)
            sd = math.sqrt(max(var, 1e-12))
        else:
            sd = 0.0

        z = {50: 0.0, 68: 1.0, 80: 1.282, 85: 1.440, 90: 1.645, 95: 1.960, 97: 2.170, 98: 2.326, 99: 2.576}.get(ci, 1.645)
        last_date = hist_dates[-1]
        for i in range(horizon):
            d = last_date + timedelta(days=i + 1)
            lo = float(ma - z * sd)
            hi = float(ma + z * sd)
            points.append({"date": d, "forecast": float(ma), "lower": lo, "upper": hi})

    return ok(
        data={"points": points},
        meta=_meta(
            source_id=sid,
            source_name=source_name,
            metric=metric,
            start_date=str(start_date) if start_date else None,
            end_date=str(end_date) if end_date else None,
            method=method_used,
            horizon=horizon,
            confidence=ci,
        ),
    )
