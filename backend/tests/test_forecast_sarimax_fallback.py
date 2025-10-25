from __future__ import annotations

import pandas as pd

from app.services import forecast


def test_train_sarimax_and_forecast_graceful_fallback(monkeypatch):
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    series = pd.Series([1.0, 2.0, 3.0], index=idx)

    monkeypatch.setattr(forecast, "SARIMAX", None, raising=False)

    df = forecast.train_sarimax_and_forecast(series, horizon_days=4)

    assert len(df) == 4
    assert all(df["yhat"] == 3.0)
    assert df.index[0] > series.index.max()
