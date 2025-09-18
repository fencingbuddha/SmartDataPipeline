# backend/app/routers/metrics.py
from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.metrics import fetch_metric_daily

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
    return rows  # FastAPI + Pydantic will serialize via from_attributes
