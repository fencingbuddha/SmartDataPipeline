from datetime import date
from app.services.forecast import fetch_metric_series, train_sarimax_and_forecast, run_forecast

def test_train_forecast_flat_series(db, seeded_metric_daily):
    s = fetch_metric_series(db, "demo-source", "value")
    df = train_sarimax_and_forecast(s, horizon_days=3)
    assert len(df) == 3
    assert "yhat" in df.columns
