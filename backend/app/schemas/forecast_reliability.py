# app/schemas/forecast_reliability.py
from datetime import date
from pydantic import BaseModel

class FoldOut(BaseModel):
    fold_index:int; mae:float; rmse:float; mape:float; bias:float

class ReliabilityOut(BaseModel):
    source_name:str; metric:str; as_of_date:date
    score:int; mape:float; rmse:float; smape:float
    folds:list[FoldOut]=[]