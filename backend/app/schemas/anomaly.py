from pydantic import BaseModel
from typing import List, Optional

class AnomalyPoint(BaseModel):
    date: str
    value: float
    is_outlier: bool
    score: float

class AnomalyResponse(BaseModel):
    points: List[AnomalyPoint]
