from __future__ import annotations
from typing import Optional, List
from datetime import date, datetime, timezone
from statistics import mean, pstdev

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import ok, fail, ResponseMeta
from app.services.metrics import fetch_metric_daily
from app.models import source as models_source

router = APIRouter(prefix="/api/metrics/anomaly", tags=["anomaly"])


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


@router.get("/iforest")
def anomaly_iforest(
    source_name: str | None = Query(None, description="Logical dataset/source name"),
    source_id: int | None = Query(None, description="Numeric source id (optional)"),
    metric: str = Query(..., description="Metric to analyze (e.g., events_total)"),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    contamination: float = Query(0.05, ge=0.001, le=0.5, description="Expected fraction of outliers"),
    db: Session = Depends(get_db),
):
    """
    Isolation Forest anomaly detection on daily metric values.
    Returns points: [{date, value, is_outlier, score}], where score > 0 => more normal.
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

    # Build series in time order
    series_dates: List[date] = []
    series_vals: List[float] = []

    def val_of(r) -> float | None:
        for k in ("value", "value_sum", "value_avg", "value_count"):
            v = getattr(r, k, None)
            if v is not None:
                return float(v)
        return None

    for r in rows:
        v = val_of(r)
        series_dates.append(r.metric_date)
        series_vals.append(v if v is not None else float("nan"))

    # If there are too few finite values, bail gracefully
    finite = [x for x in series_vals if x == x]  # NaN check
    if len(finite) < 5:
        return ok(
            data={"points": [
                {"date": d, "value": (v if v == v else None), "is_outlier": False, "score": None}
                for d, v in zip(series_dates, series_vals)
            ]},
            meta=_meta(
                source_id=sid, source_name=source_name, metric=metric,
                start_date=str(start_date) if start_date else None,
                end_date=str(end_date) if end_date else None,
                method="iforest", contamination=contamination, reason="insufficient_data"
            ),
        )

    # Fit Isolation Forest if available; otherwise fall back to rolling-z as a reasonable proxy
    points: List[dict] = []
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest

        X = np.array([[x] for x in series_vals], dtype=float)
        # Replace NaNs with local mean to avoid breaking the model
        mask = ~np.isfinite(X[:, 0])
        if mask.any():
            # simple fill with overall finite mean
            fill = float(np.nanmean(X[:, 0]))
            X[mask, 0] = fill

        model = IsolationForest(
            contamination=contamination,
            n_estimators=200,
            random_state=42,
        )
        model.fit(X)
        preds = model.predict(X)          # 1 (inlier) or -1 (outlier)
        scores = model.decision_function(X)  # higher => more normal

        for d, v, pred, sc in zip(series_dates, series_vals, preds, scores):
            points.append({
                "date": d,
                "value": (v if v == v else None),
                "is_outlier": (pred == -1),
                "score": float(sc),
            })

        method_used = "iforest"
    except Exception:
        # Fallback: rolling z-score proxy
        window = 7
        z_thresh = 3.0
        history: list[float] = []
        for d, v in zip(series_dates, series_vals):
            val = v if v == v else None
            z = None
            is_outlier = False
            if len(history) >= window and val is not None:
                last = history[-window:]
                mu = mean(last)
                sd = pstdev(last)
                if sd == 0:
                    is_outlier = (val != mu)
                    z = 0.0
                else:
                    z = (val - mu) / sd
                    is_outlier = abs(z) >= z_thresh
            points.append({
                "date": d,
                "value": val,
                "is_outlier": is_outlier,
                "score": float(z) if z is not None else None,
            })
            if val is not None:
                history.append(val)
        method_used = "rolling_z (fallback)"

    return ok(
        data={"points": points},
        meta=_meta(
            source_id=sid,
            source_name=source_name,
            metric=metric,
            start_date=str(start_date) if start_date else None,
            end_date=str(end_date) if end_date else None,
            method=method_used,
            contamination=contamination,
        ),
    )
