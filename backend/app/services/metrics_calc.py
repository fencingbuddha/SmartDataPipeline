# app/services/metrics_calc.py
from __future__ import annotations

from typing import Iterable, List, Union

from app.schemas.metrics import MetricDailyRow
from app.utils.numeric import coerce_float, coerce_int, safe_divide

RowLike = Union[MetricDailyRow, dict]

CSV_HEADER = [
    "metric_date",
    "source_id",
    "metric",
    "value",
    "value_count",
    "value_sum",
    "value_avg",
]


def row_like_to_dict(row: RowLike) -> dict:
    if isinstance(row, MetricDailyRow):
        return row.to_dict()
    return dict(row)


def normalize_metric_row(row: RowLike, agg: str = "sum") -> dict:
    """
    Produce a dict with coerced numeric fields and a unified 'value' column according to agg.
    """
    data = row_like_to_dict(row)

    value_sum = coerce_float(data.get("value_sum"))
    value_avg = coerce_float(data.get("value_avg"))
    value_count = coerce_int(data.get("value_count"))
    value_distinct = coerce_int(data.get("value_distinct"))

    computed_avg = safe_divide(value_sum, value_count)

    data["value_sum"] = value_sum
    data["value_avg"] = computed_avg if computed_avg is not None else value_avg
    data["value_count"] = value_count
    data["value_distinct"] = value_distinct

    agg_norm = (agg or "sum").lower()
    if agg_norm == "avg":
        data["value"] = data.get("value_avg")
    elif agg_norm == "count":
        data["value"] = data.get("value_count")
    else:
        data["value"] = data.get("value_sum")

    return data


def normalize_metric_rows(rows: Iterable[RowLike], agg: str = "sum") -> List[dict]:
    return [normalize_metric_row(r, agg=agg) for r in rows]


def to_csv(rows: Iterable[RowLike]) -> str:
    """
    Serialize rows to CSV with the fixed header order expected by the UI/tests.
    """
    lines = [",".join(CSV_HEADER)]

    def _fmt(value):
        return "" if value is None else str(value)

    for row in rows:
        normalized = normalize_metric_row(row, agg="sum")
        lines.append(
            ",".join(
                [
                    _fmt(normalized.get("metric_date")),
                    _fmt(normalized.get("source_id")),
                    _fmt(normalized.get("metric")),
                    _fmt(normalized.get("value")),
                    _fmt(normalized.get("value_count")),
                    _fmt(normalized.get("value_sum")),
                    _fmt(normalized.get("value_avg")),
                ]
            )
        )
    return "\n".join(lines)


__all__ = ["normalize_metric_row", "normalize_metric_rows", "row_like_to_dict", "to_csv"]
