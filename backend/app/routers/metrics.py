from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.metrics import fetch_metric_daily
from typing import Literal

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

class MetricDailyOut(BaseModel):  # inline schema, no new folder
    metric_date: date
    source_id: int
    metric: str
    value: float
    model_config = {"from_attributes": True}  # Pydantic v2

@router.get("/daily", response_model=list[MetricDailyOut])
def get_metric_daily(
    source_id: int | None = Query(None),
    metric: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
     agg: Literal["sum", "avg", "count"] = Query("sum"),
    limit: int = Query(1000, ge=1, le=10_000),
    db: Session = Depends(get_db),
):
    rows = fetch_metric_daily(
        db,
        source_id=source_id,
        metric=metric,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    if agg == "sum":
        return rows  # uses hybrid .value -> value_sum

    # remap value from other aggregates
    out = []
    for r in rows:
        v = float(r.value_avg) if agg == "avg" else float(r.value_count)
        out.append({"metric_date": r.metric_date, "source_id": r.source_id, "metric": r.metric, "value": v})
    return out
