from fastapi import APIRouter, UploadFile, File, Depends, Query, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas.common import ok, fail, meta_now

router = APIRouter(prefix="/api/upload", tags=["upload"])

@router.post("")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # ... your existing persistence / staging logic ...
    if file.content_type not in ("text/csv", "application/json"):
        return fail(code="UNSUPPORTED_TYPE", message=f"Unsupported content type {file.content_type}", status_code=415, meta=meta_now(filename=file.filename))
    # suppose we saved it and produced a staging_id
    staging_id = "stg_"  # <- replace with your real id
    return ok(
        data={"staging_id": staging_id, "filename": file.filename, "content_type": file.content_type},
        meta=meta_now(filename=file.filename)
    )

@router.post("/upload")
async def upload(
    request: Request,
    source_name: str = Query(...),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    ctype = request.headers.get("content-type", "")
    if not ctype.startswith("multipart/form-data"):
        return fail("UNSUPPORTED_MDEIA_TYPE", "Use multipart/form-data with a CSV file.", status_code=415,
                    met=meta_now(source_name=source_name))
    
    if file is None:
        return fail("NO FILE", "No file part in request.", status_code=400, meta=meta_now(source_name=source_name))
    
    # Peek to detect empty upload
    first = await file.read(1)
    await file.seek(0)
    if not first:
        return fail("EMPTY_FILE", "Uploaded file is empty.", status_code=400, meta=meta_now(source_name=source_name))
    

