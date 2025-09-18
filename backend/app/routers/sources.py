from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import Source

router = APIRouter(prefix="/api/sources", tags=["sources"])

@router.get("")
def list_sources(db: Session = Depends(get_db)):
    rows = db.query(Source).order_by(Source.id.asc()).all()
    return [{"id": s.id, "name": s.name} for s in rows]
