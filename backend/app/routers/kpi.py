from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.kpi import run_daily_kpis

router = APIRouter(prefix="/api/kpi", tags=["kpi"])

@router.post("/run")
def run_kpi(
    start: date | None = Query(None, description="If omitted, derive from data"),
    end: date | None = Query(None, description="If omitted, derive from data"),
    metric: str | None = Query(None, description="If omitted, compute ALL metrics"),
    source_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    upserted, preview = run_daily_kpis(
        db,
        start=start,
        end=end,
        metric_name=metric,
        source_id=source_id,
    )
    return {"status": "ok", "rows_upserted": upserted, "preview": preview}
