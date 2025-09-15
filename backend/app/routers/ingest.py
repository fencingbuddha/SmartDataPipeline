from fastapi import APIRouter, UploadFile, File, Query, Depends, HTTPException
from pydantic import BaseModel
from app.db.session import SessionLocal
from app.services.ingestion import ingest_file

router = APIRouter(prefix="/api", tags=["ingestion"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class IngestResponse(BaseModel):
    source: str
    raw_events_inserted: int
    clean_events_inserted: int

@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    source_name: str = Query(..., min_length=1, description="Logical source name"),
    file: UploadFile = File(...),
    db = Depends(get_db),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")

    # Only allow CSV/JSON for now
    allowed_csv = {"text/csv", "application/csv", "application/vnd.ms-excel"}
    allowed_json = {"application/json", "text/json"}
    ctype = file.content_type or "text/csv"
    if ctype not in allowed_csv | allowed_json:
        raise HTTPException(status_code=415, detail=f"Unsupported Media Type: {ctype}")

    try:
        raw_count, clean_count = ingest_file(
            db=db,
            source_name=source_name,
            file_bytes=data,
            content_type=ctype,
            filename=file.filename or "upload",
        )
        return {
            "source": source_name,
            "raw_events_inserted": raw_count,
            "clean_events_inserted": clean_count,
        }
    except HTTPException:
        raise
    except Exception as e:
        # Consistent error payload for FR-12
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
