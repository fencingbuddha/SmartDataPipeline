from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import date
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.source import Source
from app.models.forecast_results import ForecastResults
from app.services.forecast import run_forecast

router = APIRouter(prefix="/api/forecast", tags=["forecast"])

@router.post("/run")
def forecast_run(
    source_name: str = Query(..., min_length=1),
    metric: str = Query(..., min_length=1),
    # Support both ?horizon= and ?horizon_days=
    horizon_days: int | None = Query(None, ge=1, le=60),
    horizon: int | None = Query(None, ge=1, le=60),
    db: Session = Depends(get_db),
):
    # Prefer explicit horizon_days, fallback to horizon, default 7
    h = horizon_days or horizon or 7
    """
    Run forecast for (source, metric) and upsert N future daily predictions.
    Idempotent: re-running for same (source, metric, target_date) inserts 0.
    """
    try:
        n = run_forecast(db, source_name, metric, horizon_days=h)
       # Keep the envelope (new style) AND include top-level fields (legacy tests)
        return {
            "ok": True,
            "data": {"horizon_days": h, "inserted": n},
            "error": None,
            "meta": {"source": source_name, "metric": metric},
            # legacy compatibility:
            "inserted": n,
            "horizon_days": h,
        }
    except ValueError as e:
        msg = str(e)
        code = "INSUFFICIENT_HISTORY" if "INSUFFICIENT_HISTORY" in msg else "FORECAST_ERROR"
        status = 400 if code == "INSUFFICIENT_HISTORY" else 422
        raise HTTPException(status_code=status, detail={"code": code, "message": msg})

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
