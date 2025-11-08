from __future__ import annotations

import logging
import math
from datetime import date
from typing import List

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.forecast_reliability import (
    ForecastReliability,
    ForecastReliabilityFold,
)
from app.models.source import Source
from app.observability.instrument import log_job

logger = logging.getLogger(__name__)


def _load_metric_series(db: Session, source_name: str, metric: str, days: int) -> List[float]:
    """Return the most recent `days` values for a metric in chronological order."""
    try:
        from app.models.metric_daily import MetricDaily  # type: ignore

        stmt = (
            select(MetricDaily.value_sum)
            .join(Source, MetricDaily.source_id == Source.id)
            .where(
                Source.name == source_name,
                MetricDaily.metric == metric,
            )
            .order_by(desc(MetricDaily.metric_date))
            .limit(days)
        )
        vals = db.execute(stmt).scalars().all()
        return list(reversed([float(v) for v in vals]))
    except Exception:
        return []


def get_latest_reliability(
    db: Session, source_name: str, metric: str
) -> ForecastReliability | None:
    stmt = (
        select(ForecastReliability)
        .where(
            ForecastReliability.source_name == source_name,
            ForecastReliability.metric == metric,
        )
        .order_by(desc(ForecastReliability.as_of_date))
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


@log_job("forecast.reliability")
def run_reliability(
    db: Session,
    source_name: str,
    metric: str,
    days: int,
    folds: int,
    horizon: int,
) -> ForecastReliability:
    y = _load_metric_series(db, source_name, metric, days)
    n = len(y)

    horizon = max(1, int(horizon))
    max_folds = max(0, n - (horizon + 1))
    folds = max(0, min(int(folds), max_folds))

    fold_stats: List[dict] = []

    for k in range(folds):
        train_end = n - (folds - k) * horizon
        train = y[: max(train_end, 0)]
        test = y[max(train_end, 0) : max(train_end, 0) + horizon]
        if not train or not test:
            continue

        last = train[-1]
        yhat = [last] * len(test)

        abs_errs = [abs(a - p) for a, p in zip(test, yhat)]
        mae = sum(abs_errs) / len(test)
        rmse = (sum((a - p) ** 2 for a, p in zip(test, yhat)) / len(test)) ** 0.5
        mape = sum((abs(a - p) / (abs(a) + 1e-9)) for a, p in zip(test, yhat)) * 100.0 / len(test)
        smape_fold = (
            sum((2.0 * abs(a - p)) / (abs(a) + abs(p) + 1e-9) for a, p in zip(test, yhat))
            * 100.0
            / len(test)
        )
        bias = sum(p - a for a, p in zip(test, yhat)) / len(test)

        fold_stats.append(
            {
                "fold_index": int(k),
                "mae": float(mae),
                "rmse": float(rmse),
                "mape": float(mape),
                "smape": float(smape_fold),
                "bias": float(bias),
            }
        )

    def _num_ok(x: float) -> bool:
        try:
            xv = float(x)
        except Exception:
            return False
        return not (math.isnan(xv) or math.isinf(xv))

    def _avg(key: str) -> float:
        vals = [float(d[key]) for d in fold_stats if key in d and _num_ok(d[key])]
        return (sum(vals) / len(vals)) if vals else 0.0

    if fold_stats:
        mape_agg = _avg("mape")
        rmse_agg = _avg("rmse")
        smape_agg = _avg("smape")
        mape_vals = [float(d["mape"]) for d in fold_stats if "mape" in d and _num_ok(d["mape"])]
        instability = ((max(mape_vals) - min(mape_vals)) / 10.0) if len(mape_vals) >= 2 else 0.0
        score = int(max(0, min(100, 100 - (mape_agg / 2.0) - instability)))
    else:
        mape_agg = 0.0
        rmse_agg = 0.0
        smape_agg = 0.0
        score = 0

    def _safe_num(x: float) -> float:
        try:
            xv = float(x)
        except Exception:
            return 0.0
        if math.isnan(xv) or math.isinf(xv):
            return 0.0
        return xv

    mape_agg = _safe_num(mape_agg)
    rmse_agg = _safe_num(rmse_agg)
    smape_agg = _safe_num(smape_agg)

    for k, v in {"mape_agg": mape_agg, "rmse_agg": rmse_agg, "smape_agg": smape_agg}.items():
        if not isinstance(v, (int, float)) or math.isnan(float(v)) or math.isinf(float(v)):
            logger.warning("forecast_reliability: %s was non-finite (%r); coercing to 0.0", k, v)
            if k == "mape_agg":
                mape_agg = 0.0
            elif k == "rmse_agg":
                rmse_agg = 0.0
            elif k == "smape_agg":
                smape_agg = 0.0

    try:
        score = int(score)
    except Exception:
        score = 0
    score = max(0, min(100, score))

    rec = ForecastReliability(
        source_name=source_name,
        metric=metric,
        as_of_date=date.today(),
        score=int(score),
        mape=float(mape_agg),
        rmse=float(rmse_agg),
        smape=float(smape_agg),
    )
    db.add(rec)
    db.flush()

    for d in fold_stats:
        db.add(
            ForecastReliabilityFold(
                reliability_id=rec.id,
                fold_index=int(d["fold_index"]),
                mae=float(d["mae"]),
                rmse=float(d["rmse"]),
                mape=float(d["mape"]),
                bias=float(d.get("bias", 0.0)),
            )
        )

    db.commit()
    db.refresh(rec)
    return rec
