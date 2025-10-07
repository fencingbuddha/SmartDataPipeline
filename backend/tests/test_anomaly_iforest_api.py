from __future__ import annotations

from typing import Optional, List
from datetime import date, datetime, timezone
from statistics import mean, pstdev

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import ok, fail, ResponseMeta

try:
    from app.services.metrics import fetch_metric_daily_as_df  # type: ignore
except Exception:  # pragma: no cover
    fetch_metric_daily_as_df = None  # type: ignore

# Always keep DB fallback
from app.services.metrics import fetch_metric_daily  # type: ignore
from app.models import source as models_source  # type: ignore

router = APIRouter(prefix="/api/metrics/anomaly", tags=["anomaly"])


def _meta(**params) -> ResponseMeta:
    clean = {k: v for k, v in params.items() if v is not None}
    return ResponseMeta(params=clean or None, generated_at=datetime.now(timezone.utc).isoformat())


def _resolve_source_id(db: Session, source_id: Optional[int], source_name: Optional[str]) -> Optional[int]:
    if source_id is not None:
        return source_id
    if source_name:
        sid = db.query(models_source.Source.id).filter(models_source.Source.name == source_name).scalar()
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
    n_estimators: int = Query(200, ge=10, le=2000, description="IsolationForest estimators"),
    db: Session = Depends(get_db),
):
    """
    Isolation Forest anomaly detection on daily metric values.
    Returns {"points":[{"date","value","is_outlier","score"}], "anomalies":[...]}.

    Preferred path:
      - Use fetch_metric_daily_as_df() if available (tests can monkeypatch this).
    Fallback:
      - Query DB via fetch_metric_daily() and compute anomalies.
    """
    # ---------------------------
    # Preferred DF-based path
    # ---------------------------
    if fetch_metric_daily_as_df is not None:
        try:
            import numpy as np  # noqa
        except Exception:  # pragma: no cover
            np = None  # type: ignore

        try:
            import pandas as pd  # noqa
        except Exception:  # pragma: no cover
            pd = None  # type: ignore

        try:
            df = fetch_metric_daily_as_df(
                db,
                source_name=source_name,
                source_id=source_id,
                metric=metric,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception:
            df = None

        if df is not None:
            # Expect columns: metric_date, value
            try:
                df = df.sort_values("metric_date")
                dates: List[date] = [d.date() if hasattr(d, "date") else d for d in df["metric_date"].tolist()]
                # Accept either 'value' or compute from value_sum/value_avg/value_count
                if "value" in df.columns:
                    vals: List[float | None] = [float(v) if v is not None else None for v in df["value"].tolist()]
                else:
                    def _choose(row):
                        for k in ("value_sum", "value_avg", "value_count"):
                            if k in row and row[k] is not None:
                                return float(row[k])
                        return None
                    vals = [ _choose(r) for r in df.to_dict("records") ]
            except Exception:
                # If shape unexpected, return graceful empty
                return ok(
                    data={"points": [], "anomalies": []},
                    meta=_meta(
                        source_name=source_name,
                        source_id=source_id,
                        metric=metric,
                        start_date=str(start_date) if start_date else None,
                        end_date=str(end_date) if end_date else None,
                        method="iforest",
                        contamination=contamination,
                        n_estimators=n_estimators,
                        reason="bad_dataframe_shape",
                    ),
                )

            # Try IsolationForest; fallback to rolling-z if sklearn missing
            points: List[dict] = []
            method_used = "iforest"
            try:
                import numpy as np
                from sklearn.ensemble import IsolationForest

                X = np.array([[x if x is not None else np.nan] for x in vals], dtype=float)
                # Fill NaNs with global mean to avoid model errors
                col = X[:, 0]
                if np.isnan(col).any():
                    fill = float(np.nanmean(col)) if not np.isnan(col).all() else 0.0
                    col[np.isnan(col)] = fill
                    X[:, 0] = col

                model = IsolationForest(
                    contamination=contamination,
                    n_estimators=n_estimators,
                    random_state=42,
                )
                model.fit(X)
                preds = model.predict(X)             # 1 (inlier) or -1 (outlier)
                scores = model.decision_function(X)  # higher => more normal

                for d, v, pred, sc in zip(dates, vals, preds, scores):
                    points.append({
                        "date": d,
                        "value": float(v) if v is not None else None,
                        "is_outlier": bool(pred == -1),
                        # normalize so that larger => more anomalous
                        "score": float(-sc),
                    })
            except Exception:
                # Fallback to a lightweight rolling-z approach
                method_used = "rolling_z"
                window = 7
                history: list[float] = []
                for d, v in zip(dates, vals):
                    mu = None
                    sd = None
                    is_outlier = False
                    score = None
                    if len(history) >= window:
                        last = history[-window:]
                        mu = mean(last)
                        sd = pstdev(last)
                        if v is not None:
                            if sd == 0:
                                is_outlier = (v != mu)
                                score = 0.0
                            else:
                                score = (v - mu) / sd
                                is_outlier = abs(score) >= 3.0
                    points.append({
                        "date": d,
                        "value": float(v) if v is not None else None,
                        "is_outlier": is_outlier,
                        "score": float(score) if score is not None else None,
                    })
                    if v is not None:
                        history.append(v)

            anomalies = [
                {"metric_date": p["date"], "value": p["value"], "z": p.get("score")}
                for p in points if p.get("is_outlier")
            ]
            return ok(
                data={"points": points, "anomalies": anomalies},
                meta=_meta(
                    source_name=source_name,
                    source_id=source_id,
                    metric=metric,
                    start_date=str(start_date) if start_date else None,
                    end_date=str(end_date) if end_date else None,
                    method=method_used,
                    contamination=contamination,
                    n_estimators=n_estimators,
                ),
            )

    # ---------------------------
    # Fallback DB-based path
    # ---------------------------
    sid = _resolve_source_id(db, source_id, source_name)
    if source_name and sid is None:
        # In DF-path we don't 404 for unknown source (tests rely on monkeypatch),
        # but in pure-DB mode we keep a proper not-found response.
        return fail(code="UNKNOWN_SOURCE", message=f"Unknown source: {source_name}", status_code=404, meta=_meta(source_name=source_name))

    rows = fetch_metric_daily(
        db,
        source_id=sid,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        limit=10_000,
    )

    # Build series
    dates: List[date] = []
    vals: List[float | None] = []

    def val_of(r) -> float | None:
        for k in ("value", "value_sum", "value_avg", "value_count"):
            v = getattr(r, k, None)
            if v is not None:
                return float(v)
        return None

    for r in rows:
        dates.append(r.metric_date)
        vals.append(val_of(r))

    # Compute anomalies (try IsolationForest, fallback to rolling-z)
    points: List[dict] = []
    method_used = "iforest"
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest

        X = np.array([[x if x is not None else np.nan] for x in vals], dtype=float)
        col = X[:, 0]
        if np.isnan(col).any():
            fill = float(np.nanmean(col)) if not np.isnan(col).all() else 0.0
            col[np.isnan(col)] = fill
            X[:, 0] = col

        model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=42,
        )
        model.fit(X)
        preds = model.predict(X)
        scores = model.decision_function(X)

        for d, v, pred, sc in zip(dates, vals, preds, scores):
            points.append({
                "date": d,
                "value": float(v) if v is not None else None,
                "is_outlier": bool(pred == -1),
                "score": float(-sc),
            })
    except Exception:
        method_used = "rolling_z"
        window = 7
        history: list[float] = []
        for d, v in zip(dates, vals):
            mu = None
            sd = None
            is_outlier = False
            score = None
            if len(history) >= window:
                last = history[-window:]
                mu = mean(last)
                sd = pstdev(last)
                if v is not None:
                    if sd == 0:
                        is_outlier = (v != mu)
                        score = 0.0
                    else:
                        score = (v - mu) / sd
                        is_outlier = abs(score) >= 3.0
            points.append({
                "date": d,
                "value": float(v) if v is not None else None,
                "is_outlier": is_outlier,
                "score": float(score) if score is not None else None,
            })
            if v is not None:
                history.append(v)

    anomalies = [
        {"metric_date": p["date"], "value": p["value"], "z": p.get("score")}
        for p in points if p.get("is_outlier")
    ]

    return ok(
        data={"points": points, "anomalies": anomalies},
        meta=_meta(
            source_id=sid,
            source_name=source_name,
            metric=metric,
            start_date=str(start_date) if start_date else None,
            end_date=str(end_date) if end_date else None,
            method=method_used,
            contamination=contamination,
            n_estimators=n_estimators,
        ),
    )
