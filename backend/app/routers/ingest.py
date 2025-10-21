from __future__ import annotations

from typing import Optional, Dict, Iterable, Any, List
from datetime import datetime, timezone
import io, csv, json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import ok, fail, ResponseMeta
from app.models.source import Source

# tolerant ingestion + lightweight row iterators
from app.services.ingestion import (
    process_rows,
    iter_csv_bytes,
    iter_json_bytes,
    _try_clean_row,   # for strict preflight on multipart
)
from app.services.kpi import run_kpi_for_metric

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def _meta(**params) -> ResponseMeta:
    clean = {k: v for k, v in params.items() if v is not None}
    return ResponseMeta(
        params=clean or None,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def _ensure_source(db: Session, name: str) -> Source:
    src = db.query(Source).filter(Source.name == name).one_or_none()
    if not src:
        src = Source(name=name)
        db.add(src)
        db.commit()
        db.refresh(src)
    return src


def _iter_csv_text(text_data: str) -> Iterable[Dict[str, Any]]:
    """CSV DictReader that skips fully-blank lines."""
    reader = csv.DictReader(io.StringIO(text_data))
    for row in reader:
        if not any((str(v or "").strip() for v in row.values())):
            continue
        yield row


def _require_csv_header_response(text_data: str) -> Optional[JSONResponse]:
    """Return a JSON 400 response if header invalid; else None."""
    try:
        peek = csv.reader(io.StringIO(text_data))
        header = next(peek)
    except StopIteration:
        return fail(
            code="EMPTY_FILE",
            message="CSV file is empty.",
            status_code=400,
            meta=_meta(),
        )
    lower = [h.strip().lower() for h in header]
    missing = sorted(list({"timestamp", "value"} - set(lower)))
    if missing:
        return fail(
            code="MISSING_COLUMNS",
            message=f"CSV must include columns: {', '.join(missing)}.",
            status_code=400,
            details={"present": lower},
            meta=_meta(),
        )
    return None


def _multipart_csv_has_bad_rows(text_data: str, default_metric: str) -> bool:
    """Strict preflight for multipart CSV: any bad row -> fail entire request."""
    for row in _iter_csv_text(text_data):
        _clean, warn = _try_clean_row(row, default_metric=default_metric)
        if warn:
            return True
    return False


@router.post("")
async def ingest_json_or_csv(
    request: Request,
    source_name: Optional[str] = Query(None, description="Default logical source name"),
    default_metric: str = Query("events_total", description="Metric to use if rows omit 'metric'"),
    db: Session = Depends(get_db),
):
    """
    Accept raw CSV/JSON bodies or multipart CSV uploads and ingest rows into clean_events.
    Then recompute MetricDaily for the affected (source, metric).

    Rules:
    - MULTIPART CSV: strict — if any row is invalid, return 400 and do not ingest.
    - RAW CSV/JSON: tolerant — invalid rows become warnings, valid rows ingest.
    """
    ctype = (request.headers.get("content-type") or "").lower()

    # ------------------------------ MULTIPART (CSV only, strict) ------------------------------
    if "multipart/form-data" in ctype:
        form = await request.form()
        file = form.get("file")
        if file is None:
            return fail(
                code="BAD_REQUEST",
                message="No 'file' part in multipart form-data.",
                status_code=400,
                meta=_meta(),
            )

        file_ct = (getattr(file, "content_type", None) or "").lower()

        # Reject multipart JSON
        if file_ct in {"application/json", "application/ndjson", "text/json"}:
            return fail(
                code="UNSUPPORTED_MEDIA_TYPE",
                message="Send raw application/json (array or NDJSON), not multipart/form-data.",
                status_code=415,
                meta=_meta(),
            )

        if file_ct not in {"text/csv", "application/csv", "application/vnd.ms-excel"}:
            return fail(
                code="UNSUPPORTED_MEDIA_TYPE",
                message=f"Unsupported multipart file content-type: {file_ct or 'unknown'}",
                status_code=415,
                meta=_meta(),
            )

        raw = await file.read()
        if not raw or not raw.strip():
            return fail(
                code="EMPTY_FILE",
                message="CSV file is empty.",
                status_code=400,
                meta=_meta(),
            )

        try:
            text_data = raw.decode("utf-8-sig")
        except Exception:
            return fail(
                code="CSV_DECODE_ERROR",
                message="CSV must be UTF-8 encoded.",
                status_code=400,
                meta=_meta(),
            )

        # Header check
        early = _require_csv_header_response(text_data)
        if early is not None:
            return early

        # Strict preflight: any bad row -> 400
        if _multipart_csv_has_bad_rows(text_data, default_metric=default_metric):
            return fail(
                code="BAD_REQUEST",
                message="One or more CSV rows are invalid.",
                status_code=400,
                meta=_meta(params={"source_name": source_name, "filename": getattr(file, "filename", None)}),
            )

        # Ingest
        eff_source = source_name or "default"
        _ensure_source(db, eff_source)

        stats = process_rows(
            _iter_csv_text(text_data),
            source_name=eff_source,
            default_metric=default_metric,
            db=db,
            filename=(getattr(file, "filename", None) or "upload.csv"),
            content_type=file_ct or "text/csv",
        )

        # KPI recompute for ALL metrics seen
        try:
            metrics: List[str] = stats.get("metrics") or ([] if not stats.get("metric") else [stats["metric"]])
            for m in metrics:
                run_kpi_for_metric(db, source_name=eff_source, metric=m)
        except Exception:
            pass

        # Include "inserted" for back-compat
        resp = ok(
            data={
                "ingested_rows": stats["ingested_rows"],
                "inserted": stats["ingested_rows"],
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
                filename=(getattr(file, "filename", None) or "upload.csv"),
            ),
        )
        if isinstance(resp, JSONResponse):
            resp.status_code = 200
        return resp

    # ------------------------------ RAW BODY (CSV or JSON, tolerant) ------------------------------
    body: bytes = await request.body()
    if not body or not body.strip():
        return fail(
            code="EMPTY_BODY",
            message="Request body is empty. Send CSV (text/csv) or JSON (application/json).",
            status_code=400,
            meta=_meta(),
        )

    # Decide parser + infer source for JSON when not provided
    if "application/json" in ctype or "ndjson" in ctype:
        s = body.decode("utf-8-sig", errors="replace").strip()
        inferred_source = None
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                val = obj.get("source")
                if isinstance(val, str) and val.strip():
                    inferred_source = val.strip()
            elif isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict):
                        val = item.get("source")
                        if isinstance(val, str) and val.strip():
                            inferred_source = val.strip()
                            break
        except Exception:
            pass

        rows_iter = iter_json_bytes(body)
        eff_source = (source_name or inferred_source or "default")
        synthetic_name = "inline.json"
        synthetic_ct = "application/json"

    elif "text/csv" in ctype or "application/csv" in ctype or "application/vnd.ms-excel" in ctype:
        text_data = body.decode("utf-8-sig", errors="replace")
        early = _require_csv_header_response(text_data)
        if early is not None:
            return early
        rows_iter = _iter_csv_text(text_data)
        eff_source = (source_name or "default")
        synthetic_name = "inline.csv"
        synthetic_ct = "text/csv"

    else:
        s = body.decode("utf-8-sig", errors="replace").strip()
        try:
            obj = json.loads(s)
            inferred_source = None
            if isinstance(obj, dict):
                val = obj.get("source")
                if isinstance(val, str) and val.strip():
                    inferred_source = val.strip()
            elif isinstance(obj, list):
                for item in obj:
                    if isinstance(item, dict):
                        val = item.get("source")
                        if isinstance(val, str) and val.strip():
                            inferred_source = val.strip()
                            break
            rows_iter = iter_json_bytes(body)
            eff_source = (source_name or inferred_source or "default")
            synthetic_name = "inline.json"
            synthetic_ct = "application/json"
        except Exception:
            early = _require_csv_header_response(s)
            if early is not None:
                return early
            rows_iter = _iter_csv_text(s)
            eff_source = (source_name or "default")
            synthetic_name = "inline.csv"
            synthetic_ct = "text/csv"

    _ensure_source(db, eff_source)

    stats = process_rows(
        rows_iter,
        source_name=eff_source,
        default_metric=default_metric,
        db=db,
        filename=synthetic_name,  # never None
        content_type=(request.headers.get("content-type") or synthetic_ct).lower(),
    )

    try:
        metrics: List[str] = stats.get("metrics") or ([] if not stats.get("metric") else [stats["metric"]])
        for m in metrics:
            run_kpi_for_metric(db, source_name=eff_source, metric=m)
    except Exception:
        pass

    # Back-compat fields here too
    resp = ok(
        data={
            "ingested_rows": stats["ingested_rows"],
            "inserted": stats["ingested_rows"],
            "skipped_rows": stats["skipped_rows"],
            "duplicates": stats["duplicates"],
            "warnings": stats.get("warnings", []),
            "metric": stats.get("metric"),
            "metrics": stats.get("metrics", []),
            "min_ts": stats.get("min_ts"),
            "max_ts": stats.get("max_ts"),
        },
        meta=_meta(source_name=eff_source),
    )
    if isinstance(resp, JSONResponse):
        resp.status_code = 200
    return resp
