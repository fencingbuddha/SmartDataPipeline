from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field

class ForecastHealthOut(BaseModel):
    trained_at: datetime = Field(..., description="UTC time model was (re)trained")
    window: int = Field(..., description="Training window length in days")
    mape: float = Field(..., description="Mean Absolute Percentage Error (%)")

    class Config:
        from_attributes = True
