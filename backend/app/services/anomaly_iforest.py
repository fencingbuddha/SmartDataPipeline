from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

@dataclass
class IFParams:
    contamination: float = 0.05
    n_estimators: int = 100
    random_state: int = 42

def _make_features(df: pd.DataFrame) -> np.ndarray:
    """
    Expects df with column 'value' sorted by 'metric_date'.
    Returns X with simple, stable features.
    """
    v = df["value"].astype(float)
    roll_mean = v.rolling(7, min_periods=1).mean()
    roll_std = v.rolling(7, min_periods=1).std(ddof=0).fillna(0)
    diff1 = v.diff().fillna(0)
    X = np.c_[v.values, roll_mean.values, roll_std.values, diff1.values]
    return X

def detect_iforest(df: pd.DataFrame, params: IFParams) -> pd.DataFrame:
    """
    Returns original df plus columns: score, is_outlier (bool).
    """
    if df.empty:
        df = df.copy()
        df["score"] = []
        df["is_outlier"] = []
        return df

    X = _make_features(df)
    clf = IsolationForest(
        contamination=params.contamination,
        n_estimators=params.n_estimators,
        random_state=params.random_state,
    )
    clf.fit(X)
    scores = clf.decision_function(X)  # higher = more normal
    labels = clf.predict(X)            # -1 outlier, 1 inlier
    out = df.copy()
    out["score"] = scores
    out["is_outlier"] = (labels == -1)
    return out
