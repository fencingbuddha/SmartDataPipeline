from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import date
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.source import Source
from app.models.forecast_results import ForecastResults
from app.services.forecast import run_forecast

router = APIRouter(prefix="/api/forecast", tags=["forecast"])

@router.post("/run")
def forecast_run(source_name: str = Query(...), metric: str = Query(...), horizon_days: int = Query(7, ge=1, le=30), db: Session = Depends(get_db)):
    try:
        n = run_forecast(db, source_name, metric, horizon_days=horizon_days)
        return {"inserted": n, "horizon_days": horizon_days}
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.get("/daily")
def forecast_daily(source_name: str, metric: str, start_date: date, end_date: date, db: Session = Depends(get_db)):
    q = (db.query(ForecastResults)
           .join(Source, Source.id == ForecastResults.source_id)
           .filter(Source.name == source_name, ForecastResults.metric == metric)
           .filter(ForecastResults.target_date >= start_date)
           .filter(ForecastResults.target_date <= end_date)
           .order_by(ForecastResults.target_date.asc()))
    rows = q.all()
    return [{"date": r.target_date, "metric": r.metric, "yhat": r.yhat, "yhat_lower": r.yhat_lower, "yhat_upper": r.yhat_upper} for r in rows]
