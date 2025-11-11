# backend/app/routers/upload.py
from __future__ import annotations

from typing import Optional
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import structlog

from app.db.session import get_db
from app.schemas.common import ok, fail, ResponseMeta
from app.services.ingestion import process_rows, iter_csv_bytes
from app.services.kpi import run_kpi_for_metric

router = APIRouter(prefix="/api/upload", tags=["upload"])
logger = structlog.get_logger(__name__)


def _meta(**params) -> ResponseMeta:
    clean = {k: v for k, v in params.items() if v is not None}
    return ResponseMeta(
        params=clean or None,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("")
async def upload_csv(
    request: Request,
    source_name: Optional[str] = Query(None, description="Logical source name for these events"),
    default_metric: str = Query("events_total", description="Metric used if CSV rows omit 'metric'"),
    file: UploadFile = File(..., description="CSV file upload"),
    db: Session = Depends(get_db),
):
    """
    Legacy CSV upload endpoint.

    Behavior:
    - Only CSV is accepted.
    - Always records non-null filename/content_type for raw_events.
    - If the CSV has only a header row (no data), returns 200 with a lightweight
      staging payload containing a `staging_id` and empty `metrics`, without writing anything.
    """
    file_ct = (file.content_type or "").lower()
    if file_ct not in {"text/csv", "application/csv", "application/vnd.ms-excel"}:
        return fail(
            code="UNSUPPORTED_MEDIA_TYPE",
            message=f"Upload expects CSV; got {file_ct or 'unknown'}.",
            status_code=415,
            meta=_meta(),
        )

    raw_bytes = await file.read()
    if not raw_bytes or not raw_bytes.strip():
        return fail(
            code="EMPTY_FILE",
            message="CSV file is empty.",
            status_code=400,
            meta=_meta(),
        )

    # Build rows iterator from bytes (skips blank lines, tolerant)
    rows_iter = iter_csv_bytes(raw_bytes)

    eff_source = source_name or "default"
    safe_filename = (getattr(file, "filename", None) or "upload.csv")
    safe_content_type = (file_ct or "text/csv")

    # Process + store
    stats = process_rows(
        rows_iter,
        source_name=eff_source,
        default_metric=default_metric,
        db=db,
        filename=safe_filename,
        content_type=safe_content_type,
    )

    # Special case: header-only CSV (no valid or invalid rows parsed)
    if (stats.get("ingested_rows", 0) == 0) and (stats.get("skipped_rows", 0) == 0):
        staging = {
            "staging_id": str(uuid4()),
            "metrics": [],
        }
        resp = ok(
            data=staging,
            meta=_meta(source_name=eff_source, filename=safe_filename),
        )
        if isinstance(resp, JSONResponse):
            resp.status_code = 200
        return resp

    # Non-fatal KPI recompute after real ingestion
    try:
        metric = stats.get("metric") or default_metric
        if metric:
            run_kpi_for_metric(db, source_name=eff_source, metric=metric)
    except Exception as exc:
        logger.warning("upload.kpi_recompute_failed", error=str(exc), source=eff_source)

    resp = ok(
        data={
            "ingested_rows": stats["ingested_rows"],
            "inserted": stats["ingested_rows"],  # legacy field some tests expect
            "skipped_rows": stats["skipped_rows"],
            "duplicates": stats["duplicates"],
            "warnings": stats.get("warnings", []),
            "metric": stats.get("metric"),
            "metrics": stats.get("metrics", []),
            "min_ts": stats.get("min_ts"),
            "max_ts": stats.get("max_ts"),
        },
        meta=_meta(
            source_name=eff_source,
            filename=safe_filename,
        ),
    )
    if isinstance(resp, JSONResponse):
        resp.status_code = 200
    return resp
