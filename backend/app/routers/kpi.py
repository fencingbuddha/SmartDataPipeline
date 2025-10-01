from __future__ import annotations
from datetime import date
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.source import Source
from app.services.kpi import run_daily_kpis

router = APIRouter(prefix="/api/kpi", tags=["kpi"])

@router.post("/run")
def run_kpi(
    # Back-compat + nicer DX
    source_name: Optional[str] = Query(None, description="Logical source name (e.g., 'demo-source')"),
    source_id: Optional[int] = Query(None, description="Numeric source id (alternative to source_name)"),
    metric: Optional[str] = Query(None, description="If omitted, compute ALL metrics"),

    # Accept both legacy and explicit date names; prefer *_date if provided
    start_date: Optional[date] = Query(None, description="Inclusive start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Inclusive end date (YYYY-MM-DD)"),
    start: Optional[date] = Query(None, description="(deprecated alias of start_date)"),
    end: Optional[date] = Query(None, description="(deprecated alias of end_date)"),

    # NEW: aggregator + distinct
    agg: Literal["sum", "avg", "count"] = Query("sum", description="Aggregation to compute into MetricDaily"),
    distinct_field: Optional[str] = Query(None, description="Optional distinct column for distinct counts"),

    db: Session = Depends(get_db),
):
    # Resolve source_id from name if provided
    resolved_source_id: Optional[int] = source_id
    if source_name:
        src = db.query(Source).filter(Source.name == source_name).one_or_none()
        if not src:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown source: {source_name}")
        if source_id and source_id != src.id:
            raise HTTPException(status_code=400, detail="source_id does not match source_name")
        resolved_source_id = src.id

    # Choose dates (prefer explicit *_date, fall back to legacy names)
    s = start_date or start
    e = end_date or end

    upserted, preview = run_daily_kpis(
        db,
        start=s,
        end=e,
        metric_name=metric,
        source_id=resolved_source_id,
        agg=agg,                      # <— pass through
        distinct_field=distinct_field,
    )
    return {"status": "ok", "rows_upserted": upserted, "agg": agg, "preview": preview}
