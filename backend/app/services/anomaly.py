from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from statistics import mean, pstdev
from typing import Iterable, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.models.metric_daily import MetricDaily
from app.models.source import Source
from app.observability.instrument import log_job


@dataclass(frozen=True)
class SeriesPoint:
    metric_date: date
    value: Optional[float]  # None allowed; we'll skip in calc


@dataclass(frozen=True)
class AnomalyPoint:
    metric_date: date
    value: float
    z: float  # rolling z-score at this point (computed from *previous* window)


VALUE_FALLBACK_ORDER: Tuple[str, ...] = (
    "value_sum",
    "value_avg",
    "value_count",
    "value_distinct",
)


def _pick_value_field(session: Session, prefer: Optional[str] = None) -> str:
    """
    Choose which MetricDaily value_* column to read. Defaults to a sensible fallback chain.
    """
    if prefer:
        return prefer
    # default cascade, assumes columns exist on MetricDaily
    return VALUE_FALLBACK_ORDER[0]


def fetch_metric_series(
    session: Session,
    *,
    source_name: str,
    metric: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    value_field: Optional[str] = None,
) -> List[SeriesPoint]:
    """
    Pulls a date-ordered series from MetricDaily for (source_name, metric) within [start, end].
    """
    # Resolve source_id from source_name
    src = session.query(Source).filter(Source.name == source_name).one_or_none()
    if not src:
        return []

    vf = _pick_value_field(session, value_field)
    col = getattr(MetricDaily, vf, None)
    if col is None:
        # If a custom value_field is passed but doesn't exist, fall back
        for candidate in VALUE_FALLBACK_ORDER:
            col = getattr(MetricDaily, candidate, None)
            if col is not None:
                vf = candidate
                break

    q = (
        session.query(MetricDaily.metric_date, col)
        .filter(MetricDaily.source_id == src.id, MetricDaily.metric == metric)
    )

    if start_date:
        q = q.filter(MetricDaily.metric_date >= start_date)
    if end_date:
        q = q.filter(MetricDaily.metric_date <= end_date)

    q = q.order_by(MetricDaily.metric_date.asc())

    rows: List[Tuple[date, Optional[float]]] = [(d, float(v) if v is not None else None) for d, v in q.all()]
    return [SeriesPoint(metric_date=d, value=v) for d, v in rows]


def _rolling_zscores_prior_window(values: Sequence[Optional[float]], window: int) -> List[Optional[float]]:
    """
    Compute rolling z-scores using the *previous* 'window' values only (no leakage).
    For positions < window or where the prior window is not all finite, returns None.
    """
    z: List[Optional[float]] = [None] * len(values)
    if window <= 1:
        return z

    for i in range(len(values)):
        if i < window:
            continue
        prior = [v for v in values[i - window : i] if v is not None and isfinite(v)]
        if len(prior) < window:
            # if any missing within the window, skip
            continue
        mu = mean(prior)
        sigma = pstdev(prior)
        if sigma == 0 or not isfinite(sigma):
            continue
        v = values[i]
        if v is None or not isfinite(v):
            continue
        z[i] = (v - mu) / sigma
    return z


@log_job("anomaly.detect")
def detect_anomalies(
    session: Session,
    *,
    source_name: str,
    metric: str,
    start_date: Optional[date],
    end_date: Optional[date],
    window: int,
    z_thresh: float,
    value_field: Optional[str] = None,
) -> Tuple[List[SeriesPoint], List[AnomalyPoint]]:
    """
    High-level service: fetch series → compute rolling z-scores → select anomalies.
    Returns (all_points, anomalies_only).
    """
    points = fetch_metric_series(
        session,
        source_name=source_name,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        value_field=value_field,
    )

    if not points:
        return ([], [])

    values: List[Optional[float]] = [p.value for p in points]
    z = _rolling_zscores_prior_window(values, window=window)

    anomalies: List[AnomalyPoint] = []
    for i, zp in enumerate(z):
        if zp is None:
            continue
        if abs(zp) >= z_thresh and points[i].value is not None:
            anomalies.append(
                AnomalyPoint(metric_date=points[i].metric_date, value=float(points[i].value), z=float(zp))
            )

    return (points, anomalies)
