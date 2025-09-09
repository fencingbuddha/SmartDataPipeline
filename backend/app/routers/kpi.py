from fastapi import APIRouter
router = APIRouter()

@router.get("")
def list_kpis():
    return {"message": "KPIs endpoint stub"}
