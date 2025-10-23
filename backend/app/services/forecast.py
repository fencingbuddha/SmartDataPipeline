# app/services/forecast.py

from datetime import date, datetime, timedelta, timezone
from typing import Tuple, Iterable
import numpy as np
import pandas as pd
from sqlalchemy import select, asc
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sqlalchemy.orm import Session
from app.models.metric_daily import MetricDaily
from app.models.source import Source
from app.models.forecast_results import ForecastResults
from app.models.forecast_model import ForecastModel

def fetch_metric_series(db: Session, source_name: str, metric: str, start: date|None=None, end: date|None=None) -> pd.Series:
    q = (db.query(MetricDaily)
           .join(Source, Source.id == MetricDaily.source_id)
           .filter(Source.name == source_name, MetricDaily.metric == metric))
    if start: q = q.filter(MetricDaily.metric_date >= start)
    if end:   q = q.filter(MetricDaily.metric_date <= end)
    rows = q.order_by(MetricDaily.metric_date.asc()).all()
    if not rows:
        return pd.Series(dtype=float)
    idx = [r.metric_date for r in rows]
    # Use value_sum fallback (already computed in KPIs)
    vals = [r.value_sum or r.value_avg or r.value_count or 0.0 for r in rows]
    s = pd.Series(vals, index=pd.DatetimeIndex(idx, name="ds"), dtype=float)
    # fill any gaps with 0 to keep SARIMAX stable
    s = s.asfreq("D").fillna(0.0)
    return s

def train_sarimax_and_forecast(
        series: pd.Series,
        horizon_days: int = 7,
        order=(1, 1, 1),
        seasonal_order=(0, 0, 0, 0),
    ):
        # Handle empty or all-zero history safely
        if series.empty or float(series.sum()) == 0.0:
            anchor = (pd.Timestamp.utcnow().normalize() if series.empty else series.index.max()) + pd.Timedelta(days=1)
            idx = pd.date_range(anchor, periods=horizon_days, freq="D")
            return pd.DataFrame(
                {"yhat": np.zeros(horizon_days), "yhat_lower": np.zeros(horizon_days), "yhat_upper": np.zeros(horizon_days)},
                index=idx,
            )

        last_obs = series.index.max().normalize()  # << anchor from last observed day

        model = SARIMAX(
            series,
            order=order,
            seasonal_order=seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        fit = model.fit(disp=False)
        fcst = fit.get_forecast(steps=horizon_days)

        # Build our own strictly-future index to avoid any in-sample leakage
        idx = pd.date_range(last_obs + pd.Timedelta(days=1), periods=horizon_days, freq="D")

        ci = fcst.conf_int()
        df = pd.DataFrame(
            {
                "yhat": fcst.predicted_mean.to_numpy(),
                "yhat_lower": ci.iloc[:, 0].to_numpy(),
                "yhat_upper": ci.iloc[:, 1].to_numpy(),
            },
            index=idx,
        )
        # Guard against NaNs from CI on small samples
        df = df.fillna(method="ffill").fillna(0.0)
        return df


def write_forecast(db: Session, source_id: int, metric: str, df: pd.DataFrame, model_version: str = "sarimax-0.1"):
    for dt, row in df.iterrows():
        rec = (db.query(ForecastResults)
                 .filter_by(source_id=source_id, metric=metric, target_date=dt.date())
                 .one_or_none())
        if not rec:
            rec = ForecastResults(source_id=source_id, metric=metric, target_date=dt.date(), yhat=0.0)
            db.add(rec)
        rec.yhat = float(row["yhat"])
        rec.yhat_lower = float(row.get("yhat_lower", None) or 0.0)
        rec.yhat_upper = float(row.get("yhat_upper", None) or 0.0)
        rec.model_version = model_version
    db.commit()

def run_forecast(db: Session, source_name: str, metric: str, horizon_days: int = 7) -> int:
    source = db.query(Source).filter_by(name=source_name).one()
    s = fetch_metric_series(db, source_name, metric)
    MIN_POINTS = 14
    if len(s) < MIN_POINTS:
        last_val = float(s.iloc[-1]) if len(s) else 0.0
        start_day = (pd.to_datetime(s.index[-1]).date() + timedelta(days=1)) if len(s) else date.today()
        idx = pd.date_range(start=start_day, periods=horizon_days, freq="D")
        df = pd.DataFrame(
            {
                "yhat": [last_val] * horizon_days,
                "yhat_lower": [last_val] * horizon_days,
                "yhat_upper": [last_val] * horizon_days,
            },
            index=idx,
        )
    else:
        df = train_sarimax_and_forecast(s, horizon_days=horizon_days)
    write_forecast(db, source.id, metric, df)
    return len(df)

# ---------- Metrics ----------

def _mape(actuals: Iterable[float], preds: Iterable[float]) -> float:
    """
    Mean Absolute Percentage Error (%). Skips rows where actual == 0 to avoid blowups.
    Returns 100.0 if no valid comparisons.
    """
    total = 0.0
    n = 0
    for a, p in zip(actuals, preds):
        if a is None or p is None:
            continue
        if a == 0:
            continue
        total += abs((a - p) / a)
        n += 1
    if n == 0:
        return 100.0
    return 100.0 * (total / n)

def _fetch_training_series(
    db: Session, source_id: int, metric: str, n: int
) -> Tuple[list[date], list[float]]:
    q = (
        select(MetricDaily.metric_date, MetricDaily.value_sum)
        .where(MetricDaily.source_id == source_id, MetricDaily.metric == metric)
        .order_by(asc(MetricDaily.metric_date))
    )
    rows = db.execute(q).all()
    if not rows:
        return [], []
    dates = [r[0] for r in rows][-n:]
    vals = [float(r[1]) if r[1] is not None else 0.0 for r in rows][-n:]
    return dates, vals

def _naive_lacf_forecast(vals: list[float], horizon_n: int) -> list[float]:
    """Baseline: last observation carried forward."""
    last = vals[-1] if vals else 0.0
    return [last] * horizon_n

# ---------- Upsert health ----------

def upsert_forecast_health(
    db: Session,
    *,
    source_name: str,
    metric: str,
    window_n: int = 90,
    horizon_n: int = 7,
) -> ForecastModel:
    """
    Train/refresh health: compute MAPE on a simple holdout and upsert into forecast_models.
    Strategy:
      - Load last window_n + horizon_n points from metric_daily.
      - Train on window_n, predict horizon_n with baseline; compare to next horizon_n actuals -> MAPE.
    """
    src = db.execute(select(Source).where(Source.name == source_name)).scalar_one_or_none()
    if not src:
        raise ValueError(f"Unknown source_name={source_name}")

    total_needed = window_n + horizon_n
    dates_all, vals_all = _fetch_training_series(db, src.id, metric, total_needed)
    trained_at = datetime.now(timezone.utc)

    if len(vals_all) < total_needed:
        # Not enough history; still upsert a row with mape=100 to signal low reliability.
        return _upsert_model_row(
            db,
            source_id=src.id,
            metric=metric,
            window_n=window_n,
            horizon_n=horizon_n,
            trained_at=trained_at,
            train_start=dates_all[0] if dates_all else None,
            train_end=dates_all[window_n - 1] if len(dates_all) >= window_n else None,
            mape=100.0,
            model_params={"kind": "naive_lacf", "reason": "insufficient_history"},
        )

    train_vals = vals_all[:window_n]
    holdout_vals = vals_all[window_n:window_n + horizon_n]
    preds = _naive_lacf_forecast(train_vals, horizon_n)
    mape = _mape(holdout_vals, preds)

    return _upsert_model_row(
        db,
        source_id=src.id,
        metric=metric,
        window_n=window_n,
        horizon_n=horizon_n,
        trained_at=trained_at,
        train_start=dates_all[0],
        train_end=dates_all[window_n - 1],
        mape=float(mape),
        model_params={"kind": "naive_lacf", "window_n": window_n, "horizon_n": horizon_n},
    )

def _upsert_model_row(
    db: Session,
    *,
    source_id: int,
    metric: str,
    window_n: int,
    horizon_n: int,
    trained_at,
    train_start,
    train_end,
    mape: float,
    model_params: dict,
) -> ForecastModel:
    existing = db.execute(
        select(ForecastModel).where(
            ForecastModel.source_id == source_id,
            ForecastModel.metric == metric,
            ForecastModel.window_n == window_n,
        )
    ).scalar_one_or_none()

    if existing:
        existing.trained_at = trained_at
        existing.horizon_n = horizon_n
        existing.train_start = train_start
        existing.train_end = train_end
        existing.mape = mape
        existing.model_params = model_params or {}
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    fm = ForecastModel(
        source_id=source_id,
        metric=metric,
        model_name="SARIMAX",
        model_params=model_params or {},
        window_n=window_n,
        horizon_n=horizon_n,
        trained_at=trained_at,
        train_start=train_start,
        train_end=train_end,
        mape=mape,
        notes=None,
    )
    db.add(fm)
    db.commit()
    db.refresh(fm)
    return fm
