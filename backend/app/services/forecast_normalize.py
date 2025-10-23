from __future__ import annotations
from datetime import datetime, date, timezone, timedelta
from typing import Iterable, List, Dict, Any
import math

def _to_utc_midnight_z(d: str | date | datetime) -> str:
    # Accept "YYYY-MM-DD" or a date/datetime; emit "YYYY-MM-DDT00:00:00Z"
    if isinstance(d, str):
        y, m, dd = map(int, d.split("-"))
        dt = datetime(y, m, dd, tzinfo=timezone.utc)
    elif isinstance(d, date) and not isinstance(d, datetime):
        dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    else:
        dt = d.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")

def _safe_float(v: Any) -> float:
    try:
        f = float(0.0 if v is None else v)
        if math.isfinite(f):
            return f
    except Exception:
        pass
    return 0.0

def normalize_forecast_rows(raw_rows: Iterable[Dict[str, Any]], metric: str) -> List[Dict[str, Any]]:
    """Map {forecast_date, yhat, yhat_lo, yhat_hi} -> stable contract:
       {metric_date, metric, yhat, yhat_lower, yhat_upper}, UTC Z, ordered & sanitized.
    """
    out: List[Dict[str, Any]] = []
    for r in raw_rows:
        y   = _safe_float(r.get("yhat"))
        lo  = _safe_float(r.get("yhat_lo"))
        hi  = _safe_float(r.get("yhat_hi"))
        lower, upper = (lo, hi) if lo <= hi else (hi, lo)

        out.append({
            "metric_date": _to_utc_midnight_z(r.get("forecast_date")),
            "metric": metric,
            "yhat": y,
            "yhat_lower": lower,
            "yhat_upper": upper,
        })

    # Enforce exactly 7 rows, trim/pad
    out = out[:7]
    if len(out) and len(out) < 7:
        last_dt = datetime.fromisoformat(out[-1]["metric_date"].replace("Z", "+00:00"))
        for _ in range(7 - len(out)):
            last_dt += timedelta(days=1)
            out.append({
                "metric_date": last_dt.isoformat().replace("+00:00", "Z"),
                "metric": metric, "yhat": 0.0, "yhat_lower": 0.0, "yhat_upper": 0.0,
            })

    # Keep strictly ascending dates
    out.sort(key=lambda r: r["metric_date"])
    return out
