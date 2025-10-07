from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Iterable
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


@dataclass
class IFParams:
    contamination: float = 0.05
    n_estimators: int = 200
    random_state: int = 42
    window: int = 7
    std_floor: float = 1e-3  # floor to avoid division by ~0 in z-score


def _ensure_value_column(df: pd.DataFrame) -> pd.Series:
    """
    Return a numeric 'value' series for the DF, deriving from common metric_daily columns
    when 'value' is not present.
    Preference order: value, value_sum, value_avg, value_count.
    """
    if "value" in df.columns:
        s = pd.to_numeric(df["value"], errors="coerce").astype(float)
        return s

    for alt in ("value_sum", "value_avg", "value_count"):
        if alt in df.columns:
            s = pd.to_numeric(df[alt], errors="coerce").astype(float)
            return s

    # Nothing usable; return all-NaN to be handled upstream
    return pd.Series([np.nan] * len(df), index=df.index, dtype=float)


def _make_features(df: pd.DataFrame, window: int = 7, std_floor: float = 1e-3) -> np.ndarray:
    """
    Build stable features for daily KPI series.

    Expected columns:
      - metric_date (datetime-like)
      - value (numeric) OR one of (value_sum, value_avg, value_count)

    Features:
      - value
      - rolling mean (window, min_periods=window)
      - rolling std (window, min_periods=window) with epsilon floor
      - lag-1 difference
      - z = (value - roll_mean) / (roll_std + eps)

    Early rows (fewer than `window`) backfill rolling stats with global mean/std
    to avoid unstable/NaN features.
    """
    v = _ensure_value_column(df)
    eps = 1e-6

    # Compute rolling stats with strict min_periods, then backfill using global stats
    roll_mean = v.rolling(window=window, min_periods=window).mean()
    roll_std = v.rolling(window=window, min_periods=window).std(ddof=0)

    global_mean = float(np.nanmean(v.values)) if len(v) else 0.0
    # if global std ~0 or NaN, use 1.0 so z doesn't blow up
    _gstd = float(np.nanstd(v.values, ddof=0)) if len(v) else 0.0
    global_std = _gstd if _gstd > 0 else 1.0

    roll_mean = roll_mean.fillna(global_mean)
    roll_std = roll_std.fillna(global_std).clip(lower=std_floor)

    diff1 = v.diff().fillna(0.0)
    z = (v - roll_mean) / (roll_std + eps)

    X = np.c_[v.values, roll_mean.values, roll_std.values, diff1.values, z.values].astype("float64")
    return X


def _all_close(values: Iterable[float | int | None], tol: float = 1e-12) -> bool:
    """True if all non-NaN values are (nearly) identical."""
    arr = np.array([x for x in values if x is not None and not (isinstance(x, float) and np.isnan(x))], dtype=float)
    if arr.size <= 1:
        return True
    return float(np.nanstd(arr, ddof=0)) <= tol


def detect_iforest(df: pd.DataFrame, params: Optional[IFParams] = None) -> pd.DataFrame:
    """
    Detect anomalies with IsolationForest.

    Input:
      df with columns:
        - metric_date (datetime-like)
        - value (numeric) OR one of (value_sum, value_avg, value_count)

    Output:
      Same rows as input (original index preserved) with two new columns:
        - score: IsolationForest decision_function (higher = more NORMAL)
        - is_outlier: bool
    """
    params = params or IFParams()

    # Preserve original index for caller expectations
    original_index = df.index

    # Empty input → empty output with columns present
    if df.empty:
        out = df.copy()
        out["score"] = pd.Series([], dtype=float)
        out["is_outlier"] = pd.Series([], dtype=bool)
        out.index = original_index
        return out

    # Normalize/prepare
    out = df.copy()
    # Make sure metric_date exists and is sortable
    if "metric_date" not in out.columns:
        # provide a monotonic surrogate if missing to keep deterministic order
        out = out.assign(metric_date=pd.RangeIndex(start=0, stop=len(out), step=1))
    out["metric_date"] = pd.to_datetime(out["metric_date"], errors="coerce")
    out = out.sort_values("metric_date")

    # Ensure we have a usable numeric value column (even if derived)
    value_series = _ensure_value_column(out)
    out = out.assign(value=value_series)

    # If all values are NaN or the series is effectively constant, skip model and return no outliers.
    if out["value"].isna().all() or _all_close(out["value"].tolist()):
        out["score"] = 0.0
        out["is_outlier"] = False
        # restore original row order per caller’s index
        out.index = original_index
        return out

    # Build features
    X = _make_features(out, window=params.window, std_floor=params.std_floor)

    # IsolationForest expects finite numbers
    if not np.isfinite(X).all():
        # Replace remaining non-finite with column means (or zero if NaN)
        col_means = np.nanmean(np.where(np.isfinite(X), X, np.nan), axis=0)
        col_means = np.where(np.isfinite(col_means), col_means, 0.0)
        inds = ~np.isfinite(X)
        X[inds] = np.take(col_means, np.where(inds)[1])

    # Guard for tiny sample sizes: IsolationForest can misbehave with < 3 rows.
    if len(out) < 3:
        out["score"] = 0.0
        out["is_outlier"] = False
        out.index = original_index
        return out

    # Fit model
    clf = IsolationForest(
        contamination=float(params.contamination),
        n_estimators=int(params.n_estimators),
        random_state=int(params.random_state),
    )
    clf.fit(X)

    scores = clf.decision_function(X)  # higher = more normal
    labels = clf.predict(X)            # -1 outlier, 1 inlier

    out["score"] = scores.astype(float)
    out["is_outlier"] = (labels == -1)

    # Restore the caller's index
    out.index = original_index
    return out
