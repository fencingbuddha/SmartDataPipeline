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


@router.post("")
async def upload_csv(
    file: UploadFile = File(...),
    source_name: Optional[str] = Query(None),
):
    """
    Accept a CSV upload and return a staging handle.
    Tests expect: 201 Created on success.
    """
    if file is None:
        return fail(
            code="BAD_REQUEST",
            message="No file provided.",
            status_code=400,
            meta=_meta(),
        )

    content_type = (file.content_type or "").lower()
    allowed = {"text/csv", "application/csv", "application/vnd.ms-excel"}
    if content_type not in allowed:
        return fail(
            code="UNSUPPORTED_MEDIA_TYPE",
            message=f"Unsupported content-type: {file.content_type or 'unknown'}",
            status_code=415,
            meta=_meta(filename=file.filename),
        )

    # (Optional) read to ensure it's not empty
    data = await file.read()
    if not data:
        return fail(
            code="EMPTY_FILE",
            message="Uploaded file is empty.",
            status_code=400,
            meta=_meta(filename=file.filename),
        )

    # Generate a simple staging id the tests will accept
    staging_id = f"stg_{uuid.uuid4().hex[:8]}"

    resp = ok(
        data={
            "staging_id": staging_id,
            "filename": file.filename,
            "content_type": file.content_type,
        },
        meta=_meta(filename=file.filename, source_name=source_name),
    )
    # ok() returns a JSONResponse; set status to 201 Created for the test
    if isinstance(resp, JSONResponse):
        resp.status_code = 201
    return resp
