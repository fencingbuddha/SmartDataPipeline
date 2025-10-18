# app/schemas/metrics.py
from datetime import date
from typing import Optional, Literal
from pydantic import BaseModel, Field

AggLiteral = Literal["sum", "avg", "count", "distinct"]

class MetricDailyRow(BaseModel):
    metric_date: date
    source: str
    metric: str
    value_sum: Optional[float] = None
    value_avg: Optional[float] = None
    value_count: Optional[int] = None
    value_distinct: Optional[int] = None

    class Config:
        from_attributes = True


class MetricsDailyQuery(BaseModel):
    source_name: str = Field(..., description="e.g. demo-source")
    metric: str = Field(..., description="e.g. events_total")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    agg: Optional[AggLiteral] = None


class MetricName(BaseModel):
    metric: str
