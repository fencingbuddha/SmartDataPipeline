# app/utils/numeric.py
from __future__ import annotations

from typing import Optional, Union

Number = Union[int, float]


def coerce_float(value) -> Optional[float]:
    """
    Best-effort float conversion that returns None when the value cannot be parsed.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def coerce_int(value) -> Optional[int]:
    """
    Best-effort integer conversion with support for numeric strings/floats.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def safe_divide(numerator, denominator) -> Optional[float]:
    """
    Divide while guarding against None/zero/invalid values.
    """
    if numerator is None or denominator in (None, 0):
        return None
    try:
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


__all__ = ["coerce_float", "coerce_int", "safe_divide"]
