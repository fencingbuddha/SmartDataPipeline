from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.kpi import run_daily_kpis

router = APIRouter(prefix="/api/kpi", tags=["kpi"])

@router.post("/run")
def run_kpi(
    start: date | None = Query(None, description="Inclusive start (YYYY-MM-DD)"),
    end:   date | None = Query(None, description="Inclusive end (YYYY-MM-DD)"),
    metric: str = Query("default"),
    db: Session = Depends(get_db),
):
    upserted, preview = run_daily_kpis(db, start=start, end=end, metric_name=metric)
    return {"status": "ok", "rows_upserted": upserted, "preview": preview}
