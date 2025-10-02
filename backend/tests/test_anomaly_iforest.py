from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


@dataclass
class IFParams:
    contamination: float = 0.05
    n_estimators: int = 200
    random_state: int = 42


def _make_features(df: pd.DataFrame, window: int = 7) -> np.ndarray:
    """
    Build stable features for daily KPI series.

    Columns expected in df:
      - metric_date (datetime-like)
      - value (numeric)

    Features:
      - value
      - rolling mean (window)
      - rolling std (window) with epsilon floor to avoid 0
      - lag-1 difference
      - z = (value - roll_mean) / (roll_std + eps)

    We use min_periods=window to avoid unstable first points; then backfill
    with global stats so early rows don't explode.
    """
    v = pd.to_numeric(df["value"], errors="coerce").astype(float)
    eps = 1e-6

    # Use strict min_periods to avoid noisy early windows, then backfill
    roll_mean = v.rolling(window=window, min_periods=window).mean()
    roll_std = v.rolling(window=window, min_periods=window).std(ddof=0)

    # Backfill early NaNs with global stats
    global_mean = float(v.mean())
    global_std = float(v.std(ddof=0)) if float(v.std(ddof=0)) > 0 else 1.0
    roll_mean = roll_mean.fillna(global_mean)
    roll_std = roll_std.fillna(global_std)

    # Floor std to avoid division by zero & tiny variances
    roll_std = roll_std.clip(lower=1e-3)

    diff1 = v.diff().fillna(0.0)
    z = (v - roll_mean) / (roll_std + eps)

    X = np.c_[v.values, roll_mean.values, roll_std.values, diff1.values, z.values]
    return X


def detect_iforest(df: pd.DataFrame, params: Optional[IFParams] = None) -> pd.DataFrame:
    """
    Returns df with added columns:
      - score (decision_function; higher = more normal)
      - is_outlier (bool; True for anomalies)
    """
    params = params or IFParams()
    if df.empty:
        out = df.copy()
        out["score"] = []
        out["is_outlier"] = []
        return out

    # Ensure consistent order and types
    out = df.copy()
    out["metric_date"] = pd.to_datetime(out["metric_date"])
    out = out.sort_values("metric_date")

    X = _make_features(out, window=7)

    clf = IsolationForest(
        contamination=params.contamination,
        n_estimators=params.n_estimators,
        random_state=params.random_state,
    )
    clf.fit(X)
    scores = clf.decision_function(X)  # higher = more normal
    labels = clf.predict(X)            # -1 outlier, 1 inlier

    out["score"] = scores
    out["is_outlier"] = (labels == -1)

    out.index = df.index
    return out