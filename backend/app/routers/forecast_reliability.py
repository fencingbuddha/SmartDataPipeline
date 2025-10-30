# app/routers/forecast_reliability.py
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select
from pydantic import BaseModel

from app.db.session import get_db
from app.schemas.forecast_reliability import ReliabilityOut
from app.services.forecast_reliability import get_latest_reliability, run_reliability
from app.models.forecast_reliability import ForecastReliability


class RunIn(BaseModel):
    source_name: str
    metric: str
    days: int = 90
    folds: int = 5
    horizon: int = 7


router = APIRouter(prefix="/api/forecast/reliability", tags=["forecast"])


@router.get("", response_model=ReliabilityOut)
def read_reliability(
    source_name: str = Query(...),
    metric: str = Query(...),
    db: Session = Depends(get_db),
):
    row = get_latest_reliability(db, source_name, metric)
    if not row:
        raise HTTPException(status_code=404, detail="No reliability computed yet")
    return ReliabilityOut(
        source_name=row.source_name,
        metric=row.metric,
        as_of_date=row.as_of_date,
        score=row.score,
        mape=row.mape,
        rmse=row.rmse,
        smape=row.smape,
        folds=[
            {
                "fold_index": f.fold_index,
                "mae": f.mae,
                "rmse": f.rmse,
                "mape": f.mape,
                "bias": f.bias,
            }
            for f in row.folds
        ],
    )


@router.post("/run")
def run_recalc(body: RunIn, db: Session = Depends(get_db)):
    try:
        rec = run_reliability(
            db,
            body.source_name,
            body.metric,
            body.days,
            body.folds,
            body.horizon,
        )
        # Reload with folds eagerly loaded
        rec = (
            db.execute(
                select(ForecastReliability)
                .options(selectinload(ForecastReliability.folds))
                .where(ForecastReliability.id == rec.id)
            )
            .scalars()
            .first()
        )

        if not rec or not rec.folds:
            raise HTTPException(
                status_code=422,
                detail="Reliability run produced 0 folds. Check data window and folds/horizon values.",
            )

        n = len(rec.folds)
        avg = lambda xs: float(sum(xs) / n) if n else 0.0
        payload = {
            "ok": True,
            "data": {
                "folds": n,
                "avg_mae": avg([f.mae for f in rec.folds]),
                "avg_rmse": avg([f.rmse for f in rec.folds]),
                "avg_mape": avg([f.mape for f in rec.folds]),
                "avg_smape": float(rec.smape or 0.0),
                "score": int(rec.score),
            },
            "meta": {
                "source_name": rec.source_name,
                "metric": rec.metric,
                "folds": n,
                "horizon": body.horizon,
                "window_n": body.days,
            },
        }
        return JSONResponse(payload, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
