# backend/app/routers/metrics.py
from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Literal, Optional, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi.responses import StreamingResponse
import io, csv
from statistics import mean, pstdev

from app.db.session import get_db
from app.models import source as models_source
from app.services.metrics import fetch_metric_daily
from app.schemas.common import ok, fail, ResponseMeta  # <- envelope helpers

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


class MetricDailyOut(BaseModel):
    metric_date: date
    source_id: int
    metric: str
    # Full shape for UI tiles/table (optional so we stay tolerant)
    value_sum: Optional[float] = None
    value_avg: Optional[float] = None
    value_count: Optional[int] = None
    value_distinct: Optional[int] = None
    # Legacy/simplified single value (chart uses this)
    value: Optional[float] = None

    model_config = {"from_attributes": True}  # Pydantic v2


# --------- helpers ---------
def _resolve_source_id(db: Session, source_id: int | None, source_name: str | None) -> int | None:
    if source_id is not None:
        return source_id
    if source_name:
        sid = db.query(models_source.Source.id)\
                .filter(models_source.Source.name == source_name)\
                .scalar()
        return sid
    return None

def _meta(**params) -> ResponseMeta:
    # include only non-None params
    clean_params = {k: v for k, v in params.items() if v is not None}
    return ResponseMeta(
        params=clean_params,
        generated_at=datetime.now(timezone.utc).isoformat()
    )


# --------- endpoints ---------
@router.get("/names")
def list_metric_names(
    source_name: str | None = Query(None),
    source_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    sid = _resolve_source_id(db, source_id, source_name)
    if source_name and sid is None:
        # unknown source -> enveloped 404
        return fail(code="UNKNOWN_SOURCE", message=f"Unknown source: {source_name}", status_code=404, meta=_meta(source_name=source_name))

    rows = db.execute(
        text("""
            SELECT DISTINCT metric
            FROM metric_daily
            WHERE (:sid IS NULL OR source_id = :sid)
            ORDER BY metric
        """),
        {"sid": sid},
    )
    try:
        names: List[str] = rows.scalars().all()
    except Exception:
        names = [r[0] for r in rows.fetchall()]

    return ok(names, meta=_meta(source_id=sid, source_name=source_name))


@router.get("/daily")
def get_metric_daily(
    # UI usually sends source_name; keep source_id for power users/tests
    source_name: str | None = Query(None),
    source_id: int | None = Query(None),
    metric: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    distinct_field: str | None = Query(None),  # passthrough if your service uses it
    agg: Literal["sum", "avg", "count"] = Query("sum"),
    limit: int = Query(1000, ge=1, le=10_000),
    db: Session = Depends(get_db),
):
    sid = _resolve_source_id(db, source_id, source_name)

    # 👉 Return 200 + empty list if the named source doesn't exist
    if source_name and sid is None:
        return ok(
            data=[],
            meta=_meta(
                source_id=None,
                source_name=source_name,
                metric=metric,
                start_date=str(start_date) if start_date else None,
                end_date=str(end_date) if end_date else None,
                distinct_field=distinct_field,
                agg=agg,
                limit=limit,
                reason="unknown_source",
            ),
        )

    rows = fetch_metric_daily(
        db,
        source_id=sid,
        metric=metric,
        start_date=start_date,
        end_date=end_date,  # service should treat end_date as inclusive (<=)
        limit=limit,
        # distinct_field=distinct_field,  # uncomment if your service supports it
    )

    out: list[MetricDailyOut] = []
    for r in rows:
        value_sum = getattr(r, "value_sum", None)
        value_avg = getattr(r, "value_avg", None)
        value_count = getattr(r, "value_count", None)
        value_distinct = getattr(r, "value_distinct", None)

        # Preserve existing agg behavior for the single `value` field
        if agg == "avg" and value_avg is not None:
            single_value = float(value_avg)
        elif agg == "count" and value_count is not None:
            single_value = float(value_count)
        else:
            single_value = (
                float(value_sum) if value_sum is not None else
                (float(value_avg) if value_avg is not None else
                 (float(value_count) if value_count is not None else None))
            )

        out.append(
            MetricDailyOut(
                metric_date=r.metric_date,
                source_id=r.source_id,
                metric=r.metric,
                value_sum=value_sum,
                value_avg=value_avg,
                value_count=value_count,
                value_distinct=value_distinct,
                value=single_value,
            )
        )

    return ok(
        data=out,
        meta=_meta(
            source_id=sid,
            source_name=source_name,
            metric=metric,
            start_date=str(start_date) if start_date else None,
            end_date=str(end_date) if end_date else None,
            distinct_field=distinct_field,
            agg=agg,
            limit=limit,
        ),
    )



@router.get("/export/csv")
def export_metrics_csv(
    source_name: str | None = Query(None),
    source_id: int | None = Query(None),
    metric: str = Query(...),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db: Session = Depends(get_db),
):
    # CSV is a file download; keep it streaming (not enveloped)
    sid = _resolve_source_id(db, source_id, source_name)
    if source_name and sid is None:
        # Return a tiny CSV explaining the error (avoid HTML error page in a CSV download)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["error", "message"])
        w.writerow(["UNKNOWN_SOURCE", f"Unknown source: {source_name}"])
        headers = {"Content-Disposition": 'attachment; filename="metric_daily_error.csv"'}
        return StreamingResponse(io.BytesIO(buf.getvalue().encode("utf-8")), media_type="text/csv", headers=headers)

    rows = fetch_metric_daily(
        db,
        source_id=sid,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        limit=10_000,
    )

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["metric_date","source_id","metric","value_sum","value_avg","value_count","value_distinct","value"])
    for r in rows:
        w.writerow([
            r.metric_date,
            r.source_id,
            r.metric,
            getattr(r, "value_sum", None),
            getattr(r, "value_avg", None),
            getattr(r, "value_count", None),
            getattr(r, "value_distinct", None),
            getattr(r, "value", getattr(r, "value_sum", None)),
        ])

    headers = {"Content-Disposition": 'attachment; filename="metric_daily.csv"'}
    return StreamingResponse(io.BytesIO(buf.getvalue().encode("utf-8")), media_type="text/csv", headers=headers)


@router.get("/anomaly/rolling")
def rolling_anomaly(
    source_name: str | None = Query(None),
    source_id: int | None = Query(None),
    metric: str = Query(...),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    window: int = Query(7, ge=2, le=60),
    z_thresh: float = Query(3.0, ge=0.5, le=10),
    db: Session = Depends(get_db),
):
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

    history: list[float] = []
    points: list[dict] = []

    def val_of(r) -> float | None:
        for k in ("value", "value_sum", "value_avg", "value_count"):
            v = getattr(r, k, None)
            if v is not None:
                return float(v)
        return None

    for r in rows:
        v = val_of(r)
        mu = None
        sd = None
        is_outlier = False
        score = None  # normalized z-score if available

        if len(history) >= window:
            last = history[-window:]
            mu = mean(last)
            sd = pstdev(last)  # population stdev; 0.0 if flat
            if v is not None:
                if sd == 0:
                    is_outlier = (v != mu)
                    score = 0.0
                else:
                    score = (v - mu) / sd
                    is_outlier = abs(score) >= z_thresh

        points.append({
            "date": r.metric_date,
            "value": v,
            "is_outlier": is_outlier,
            "score": float(score) if score is not None else None,
        })

        if v is not None:
            history.append(v)

    return ok(
        data={"points": points},
        meta=_meta(
            source_id=sid,
            source_name=source_name,
            metric=metric,
            start_date=str(start_date) if start_date else None,
            end_date=str(end_date) if end_date else None,
            method="rolling_z",
            window=window,
            z_threshold=z_thresh,
        ),
    )
