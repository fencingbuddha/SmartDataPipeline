# app/services/forecast.py

from datetime import date, datetime, timedelta, timezone
from typing import Tuple, Iterable, List
import numpy as np
import pandas as pd
from sqlalchemy import select, asc
try:
    from statsmodels.tsa.statespace.sarimax import SARIMAX
except (ImportError, OSError) as exc:  # pragma: no cover - platform-specific wheel issues
    SARIMAX = None
    _SARIMAX_IMPORT_ERROR = exc
else:
    _SARIMAX_IMPORT_ERROR = None
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

        if SARIMAX is None:
            # degrade gracefully when the optional statsmodels wheel is unavailable
            idx = pd.date_range(last_obs + pd.Timedelta(days=1), periods=horizon_days, freq="D")
            return pd.DataFrame(
                {
                    "yhat": np.full(horizon_days, float(series.iloc[-1])),
                    "yhat_lower": np.zeros(horizon_days),
                    "yhat_upper": np.zeros(horizon_days),
                },
                index=idx,
            )

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


def _mape(actual: pd.Series, pred: pd.Series, eps: float = 1e-6) -> float:
    actual, pred = actual.align(pred, join="inner")
    if len(actual) == 0:
        return 100.0
    denom = actual.abs().clip(lower=eps)
    return float(((actual - pred).abs() / denom).mean() * 100.0)


# ------------------ Rolling Backtest Helpers ------------------

def _mae(a: Iterable[float], p: Iterable[float]) -> float:
    a = np.asarray(list(a), dtype=float); p = np.asarray(list(p), dtype=float)
    return float(np.mean(np.abs(a - p)))

def _rmse(a: Iterable[float], p: Iterable[float]) -> float:
    a = np.asarray(list(a), dtype=float); p = np.asarray(list(p), dtype=float)
    return float(np.sqrt(np.mean((a - p) ** 2)))

def _smape(a: Iterable[float], p: Iterable[float]) -> float:
    a = np.asarray(list(a), dtype=float); p = np.asarray(list(p), dtype=float)
    denom = np.abs(a) + np.abs(p)
    denom = np.where(denom == 0.0, 1.0, denom)
    return float(100.0 * np.mean(np.abs(a - p) / denom))

def _forecast_vector(train: pd.Series, horizon: int) -> List[float]:
    # Use SARIMAX if available and we have enough points; otherwise naive last-value
    MIN_POINTS = 14
    if SARIMAX is None or len(train) < MIN_POINTS:
        last = float(train.iloc[-1]) if len(train) else 0.0
        return [last] * horizon
    try:
        model = SARIMAX(
            train,
            order=(1, 1, 1),
            seasonal_order=(0, 0, 0, 0),
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        fit = model.fit(disp=False)
        fc = fit.forecast(steps=horizon)
        return [float(x) for x in fc.tolist()]
    except Exception:
        last = float(train.iloc[-1]) if len(train) else 0.0
        return [last] * horizon

def _split_rolling_origin(series: pd.Series, fold_idx: int, horizon: int) -> tuple[pd.Series, pd.Series]:
    """
    For fold t: test is the (t+1)-th block of size horizon from the end.
    """
    start = len(series) - (fold_idx + 1) * horizon
    if start <= 0:
        return series.iloc[:0], series.iloc[0:0]
    train = series.iloc[:start]
    test = series.iloc[start : start + horizon]
    return train, test

def run_rolling_backtest(
    db: Session,
    source_name: str,
    metric: str,
    *,
    folds: int = 5,
    horizon: int = 7,
    window_n: int = 90,
) -> dict:
    """
    Expanding-window rolling-origin backtest with aggregate metrics and a 0–100 score.
    Returns: {'folds', 'avg_mae', 'avg_rmse', 'avg_mape', 'avg_smape', 'score'}
    """
    series_all = fetch_metric_series(db, source_name, metric)
    if series_all.empty:
        return {"folds": 0, "avg_mae": None, "avg_rmse": None, "avg_mape": None, "avg_smape": None, "score": 0}

    need = window_n + folds * horizon
    series = series_all.tail(need)

    results = []
    for t in range(folds):
        train, test = _split_rolling_origin(series, t, horizon)
        if len(test) < horizon or len(train) < 8:
            break
        pred = _forecast_vector(train, horizon)
        y_true = test.values.astype(float)[: len(pred)]
        mae = _mae(y_true, pred)
        rmse = _rmse(y_true, pred)
        mape = _mape(pd.Series(y_true), pd.Series(pred))
        smape = _smape(y_true, pred)
        results.append({"mae": mae, "rmse": rmse, "mape": mape, "smape": smape})

    if not results:
        return {"folds": 0, "avg_mae": None, "avg_rmse": None, "avg_mape": None, "avg_smape": None, "score": 0}

    avgs = {
        "avg_mae": float(np.mean([r["mae"] for r in results])),
        "avg_rmse": float(np.mean([r["rmse"] for r in results])),
        "avg_mape": float(np.mean([r["mape"] for r in results])),
        "avg_smape": float(np.mean([r["smape"] for r in results])),
    }
    score = max(0.0, min(100.0, 100.0 - (avgs["avg_mape"] + avgs["avg_smape"]) / 2.0))
    return {"folds": len(results), **avgs, "score": float(score)}



def upsert_forecast_health(
    db: Session, *, source_name: str, metric: str, window_n: int = 90
):
    """Lightweight health: MAPE of naive one-step persistence over last N days.
    Returns a SimpleNamespace(trained_at, window_n, mape)."""
    from types import SimpleNamespace
    s = fetch_metric_series(db, source_name, metric)
    if s.empty or len(s) < 2:
        mape = 100.0
    else:
        s = s.tail(window_n + 1)
        pred = s.shift(1).dropna()
        actual = s.iloc[1:]
        mape = _mape(actual, pred)
    return SimpleNamespace(trained_at=datetime.now(timezone.utc), window_n=int(window_n), mape=float(mape))
