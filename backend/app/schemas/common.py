from __future__ import annotations
from typing import Any, Dict, Optional
from fastapi import status as http
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime, timezone
from fastapi.encoders import jsonable_encoder

class ApiError(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

class ResponseMeta(BaseModel):
    source_name: Optional[str] = None
    metric: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    generated_at: str
    version: str = "0.7.0"

class Envelope(BaseModel):
    ok: bool                              # <-- canonical flag
    data: Any | None = None
    error: ApiError | None = None
    meta: ResponseMeta

def ok(data: Any = None, meta: Optional[ResponseMeta] = None, status_code: int = http.HTTP_200_OK) -> JSONResponse:
    """
    Return unified success envelope. Pass meta through as-is (don't re-wrap).
    """
    if meta is None:
        meta = ResponseMeta(generated_at=datetime.now(timezone.utc).isoformat())
    payload = Envelope(ok=True, data=data, error=None, meta=meta).model_dump()
    return JSONResponse(content=jsonable_encoder(payload), status_code=status_code)

def fail(
    code: str,
    message: str,
    status_code: int = http.HTTP_400_BAD_REQUEST,
    details: Optional[Dict[str, Any]] = None,
    meta: Optional[ResponseMeta] = None,
) -> JSONResponse:
    """
    Return unified error envelope with ok=False.
    """
    if meta is None:
        meta = ResponseMeta(generated_at=datetime.now(timezone.utc).isoformat())
    payload = Envelope(
        ok=False,
        data=None,
        error=ApiError(code=code, message=message, details=details),
        meta=meta,
    ).model_dump()
    return JSONResponse(content=payload, status_code=status_code)

def meta_now(*, source_name: Optional[str] = None, metric: Optional[str] = None, **params) -> ResponseMeta:
    clean = {k: v for k, v in params.items() if v is not None}
    return ResponseMeta(
        source_name=source_name,
        metric=metric,
        params=clean or None,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
