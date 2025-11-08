# app/schemas/metrics.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

AggLiteral = Literal["sum", "avg", "count", "distinct"]


@dataclass
class MetricDailyRow(dict):
    """
    Dict-like DTO that also provides attribute access for compatibility with tests/router logic.
    """

    __slots__ = ()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as ex:
            raise AttributeError(name) from ex

    def to_dict(self) -> dict:
        return dict(self)


class MetricDailyRowModel(BaseModel):
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


__all__ = [
    "AggLiteral",
    "MetricDailyRow",
    "MetricDailyRowModel",
    "MetricsDailyQuery",
    "MetricName",
]
