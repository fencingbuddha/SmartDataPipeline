from fastapi import APIRouter, UploadFile, File, Query, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
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
    inserted: int
    duplicates: int
    raw_events_inserted: int
    clean_events_inserted: int

@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    request: Request,
    source_name: str = Query(..., min_length=1),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    # CSV via multipart
    if file is not None:
        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="Empty file.")
        allowed = {"text/csv", "application/csv", "application/vnd.ms-excel", "application/json", "text/json"}
        ctype = file.content_type or "text/csv"
        if ctype not in allowed:
            raise HTTPException(status_code=415, detail=f"Unsupported Media Type: {ctype}")

        raw_count, inserted, duplicates = ingest_file(db, source_name, data, ctype, file.filename or "upload")
        return {"source": source_name, "inserted": inserted, "duplicates": duplicates,
                "raw_events_inserted": raw_count, "clean_events_inserted": inserted}

    # Raw JSON body
    if request.headers.get("content-type", "").startswith("application/json"):
        body = await request.body()
        if not body:
            raise HTTPException(status_code=400, detail="Empty body.")
        raw_count, inserted, duplicates = ingest_file(db, source_name, body, "application/json", "body.json")
        return {"source": source_name, "inserted": inserted, "duplicates": duplicates,
                "raw_events_inserted": raw_count, "clean_events_inserted": inserted}

    raise HTTPException(status_code=415, detail="Provide CSV file or JSON body")