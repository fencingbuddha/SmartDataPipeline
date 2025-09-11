from fastapi import APIRouter, UploadFile, File, Query, Depends, HTTPException
from app.db.session import SessionLocal
from app.services.ingestion import ingest_file

router = APIRouter(prefix="/api", tags=["ingestion"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/ingest")
async def ingest(
    source_name: str = Query(..., min_length=1),
    file: UploadFile = File(...),
    db = Depends(get_db),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    raw_count, clean_count = ingest_file(
        db=db,
        source_name=source_name,
        file_bytes=data,
        content_type=file.content_type or "text/csv",
        filename=file.filename or "upload.csv",
    )
    db.commit()
    return {
        "source": source_name,
        "raw_events_inserted": raw_count,
        "clean_events_inserted": clean_count,
    }
