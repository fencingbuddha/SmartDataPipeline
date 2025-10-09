from datetime import date, timedelta
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sqlalchemy.orm import Session
from app.models.metric_daily import MetricDaily
from app.models.source import Source
from app.models.forecast_results import ForecastResults

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
        # If empty, anchor from "tomorrow" in UTC; if not empty, anchor from last date + 1
        anchor = (
            pd.Timestamp.utcnow().normalize()
            if series.empty
            else series.index.max()
        ) + pd.Timedelta(days=1)

        idx = pd.date_range(anchor, periods=horizon_days, freq="D")
        return pd.DataFrame(
            {
                "yhat": np.zeros(horizon_days),
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
    df = pd.DataFrame(
        {
            "yhat": fcst.predicted_mean,
            "yhat_lower": fcst.conf_int().iloc[:, 0],
            "yhat_upper": fcst.conf_int().iloc[:, 1],
        },
        index=fcst.row_labels,
    )
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
