from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.source import Source
from app.schemas.common import ok, fail, meta_now

router = APIRouter(prefix="/api/sources", tags=["sources"])

@router.get("")
def list_sources(db: Session = Depends(get_db)):
    rows = db.query(Source).order_by(Source.name.asc()).all()
    # you can return ORM objects; FastAPI will serialize, or map to DTO if you have one
    return ok(data=[{"id": r.id, "name": r.name} for r in rows], meta=meta_now())

@router.get("/{source_id}")
def get_source(source_id: int, db: Session = Depends(get_db)):
    r = db.query(Source).get(source_id)
    if not r:
        # either raise HTTPException(...) or use fail(...)
        return fail(code="NOT_FOUND", message=f"Source {source_id} not found", status_code=404, meta=meta_now(source_id=source_id))
    return ok(data={"id": r.id, "name": r.name}, meta=meta_now(source_id=source_id))
