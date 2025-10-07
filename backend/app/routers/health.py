from fastapi import APIRouter
from app.schemas.common import ok, meta_now

router = APIRouter(prefix="/api/health", tags=["health"])

@router.get("")
def healthcheck():
    return ok(
        data={"status": "ok"}, 
        meta=meta_now()
    )
