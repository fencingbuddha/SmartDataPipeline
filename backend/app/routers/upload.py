from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Dict

import csv
import io
import json

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Source, RawEvent

router = APIRouter(prefix="/api", tags=["upload"])

ACCEPTED_EXTS = (".csv", ".json")
ACCEPTED_CT = {"text/csv", "application/json", "text/json"}


def _ext_ok(name: str) -> bool:
    return name.lower().endswith(ACCEPTED_EXTS)


def _ct_ok(ct: str | None) -> bool:
    return (ct or "").lower() in ACCEPTED_CT


def _parse_csv(b: bytes) -> List[Dict]:
    buf = io.StringIO(b.decode("utf-8", errors="replace"))
    reader = csv.DictReader(buf)
    return [dict(r) for r in reader]


def _parse_json(b: bytes) -> List[Dict]:
    data = json.loads(b.decode("utf-8", errors="replace"))
    if isinstance(data, list):
        return [d if isinstance(d, dict) else {"value": d} for d in data]
    if isinstance(data, dict):
        return [data]
    return [{"value": data}]


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile = File(...),
    source_name: str = Query(..., description="Logical data source label"),
    db: Session = Depends(get_db),
):
    # Validate file type
    if not _ext_ok(file.filename) and not _ct_ok(file.content_type):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Only CSV/JSON allowed. Got {file.filename} {file.content_type}",
        )

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty upload")

    # Parse
    try:
        if file.filename.lower().endswith(".csv") or (file.content_type or "").lower() == "text/csv":
            rows = _parse_csv(raw_bytes)
        else:
            rows = _parse_json(raw_bytes)
    except Exception as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Failed to parse file: {e}")

    if not rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No records parsed from file")

    # Upsert source
    src = db.query(Source).filter(Source.name == source_name).one_or_none()
    if src is None:
        src = Source(name=source_name)
        db.add(src)
        db.flush()  # assigns src.id

    # Insert raw events
    objs = [
        RawEvent(
            source_id=src.id,
            filename=file.filename,
            content_type=(file.content_type or "application/octet-stream"),
            payload=row,
            received_at=datetime.now(timezone.utc),
        )
        for row in rows
    ]

    db.add_all(objs)
    db.commit()

    return {
        "source": source_name,
        "filename": file.filename,
        "content_type": file.content_type,
        "records_ingested": len(objs),
        "message": "Upload ingested into raw_events.",
    }
