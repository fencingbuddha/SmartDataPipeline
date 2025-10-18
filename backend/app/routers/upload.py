# backend/app/routers/upload.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid

from fastapi import APIRouter, File, UploadFile, Query
from fastapi.responses import JSONResponse

from app.schemas.common import ok, fail, ResponseMeta

router = APIRouter(prefix="/api/upload", tags=["upload"])


def _meta(**params) -> ResponseMeta:
    clean = {k: v for k, v in params.items() if v is not None}
    return ResponseMeta(
        params=clean or None,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

CSV_MIME = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
}
JSON_MIME = {
    "application/json",
    "text/json",
    "application/ld+json",
}
NDJSON_MIME = {
    "application/x-ndjson",
    "application/ndjson",
    "application/json-seq",
}

def _infer_kind(filename: str | None, content_type: str | None, sample: bytes) -> str:
    """
    Returns 'csv' | 'json' | 'ndjson' (defaults to 'csv' for compatibility).
    """
    ct = (content_type or "").lower()
    name = (filename or "").lower()

    if ct in CSV_MIME:   return "csv"
    if ct in JSON_MIME:  return "json"
    if ct in NDJSON_MIME:return "ndjson"

    if name.endswith(".csv"):    return "csv"
    if name.endswith(".json"):   return "json"
    if name.endswith(".ndjson"): return "ndjson"

    first = sample.lstrip()[:1]
    if first in (b"[", b"{"):    return "json"
    if b"\n" in sample:
        first_line = sample.splitlines()[0].strip()
        if first_line.startswith(b"{") and first_line.endswith(b"}"):
            return "ndjson"

    return "csv"


@router.post("")
async def upload_csv(
    file: UploadFile = File(...),
    source_name: Optional[str] = Query(None),
):
    """
    Accept CSV, JSON array, or NDJSON upload and return a staging handle.
    Rules:
      - CSV with header only (no data rows) => 200 OK
      - All other successful uploads       => 201 Created
    """
    if file is None:
        return fail(
            code="BAD_REQUEST",
            message="No file provided.",
            status_code=400,
            meta=_meta(),
        )

    # Read some bytes for sniffing + full payload for simple checks
    head = await file.read(2048)
    rest = await file.read()
    data = head + rest

    if not data:
        return fail(
            code="EMPTY_FILE",
            message="Uploaded file is empty.",
            status_code=400,
            meta=_meta(filename=file.filename, source_name=source_name),
        )

    kind = _infer_kind(file.filename, file.content_type, head)
    if kind not in {"csv", "json", "ndjson"}:
        return fail(
            code="UNSUPPORTED_MEDIA_TYPE",
            message=f"Unsupported content-type or format: {file.content_type or 'unknown'}",
            status_code=415,
            meta=_meta(filename=file.filename, source_name=source_name),
        )

    # Decide status code: special case for header-only CSV => 200
    status_code = 201
    if kind == "csv":
        # Treat as UTF-8 with BOM tolerance; ignore undecodable bytes
        text = data.decode("utf-8-sig", errors="replace")
        non_empty_lines = [ln for ln in text.splitlines() if ln.strip() != ""]
        # If there are 0 lines, earlier "empty" would have caught it.
        # If there is exactly 1 non-empty line (header only), return 200.
        if len(non_empty_lines) == 1:
            status_code = 200

    staging_id = f"stg_{uuid.uuid4().hex[:8]}"

    resp = ok(
        data={
            "staging_id": staging_id,
            "filename": file.filename,
            "content_type": file.content_type,
            "kind": kind,  # harmless extra for debugging/telemetry
        },
        meta=_meta(filename=file.filename, source_name=source_name),
    )
    if isinstance(resp, JSONResponse):
        resp.status_code = status_code
    return resp
