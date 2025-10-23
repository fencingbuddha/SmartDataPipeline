from datetime import date, datetime, timedelta, timezone
import math
import time


def _parse_utc_z(s: str) -> datetime:
    # Accept "YYYY-MM-DDT00:00:00Z"
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_forecast_daily_contract_and_behavior(client, seeded_metric_daily):
    """
    The /api/forecast/daily endpoint:
      - always returns exactly 7 rows
      - emits UTC 'Z' timestamps (midnight)
      - dates are strictly increasing and contiguous by 1 day
      - yhat_lower <= yhat <= yhat_upper
      - no NaN/inf values
    NOTE: /api/forecast/run no longer exists; /daily performs generation internally.
    """
    t0 = time.time()
    r = client.get(
        "/api/forecast/daily",
        params={"source_name": "demo-source", "metric": "value"},
    )
    assert r.status_code == 200, r.text
    data = r.json()

    # Shape
    assert isinstance(data, list) and len(data) == 7
    required_keys = {"metric_date", "metric", "yhat", "yhat_lower", "yhat_upper"}
    for row in data:
        assert required_keys.issubset(row.keys())
        assert row["metric"] == "value"

    # Bands ordered + numbers are finite
    for row in data:
        for k in ("yhat", "yhat_lower", "yhat_upper"):
            v = row[k]
            assert v is not None
            assert isinstance(v, (int, float))
            assert math.isfinite(float(v))
        assert row["yhat_lower"] <= row["yhat"] <= row["yhat_upper"]

    # UTC Z + strictly increasing + contiguous
    dts = [_parse_utc_z(row["metric_date"]) for row in data]
    assert all(dt.tzinfo is not None and dt.utcoffset() == timedelta(0) for dt in dts)
    assert all(dts[i] < dts[i + 1] for i in range(len(dts) - 1))
    assert all((dts[i + 1] - dts[i]) == timedelta(days=1) for i in range(len(dts) - 1))

    # Seeded fixture last observed is 2025-09-30 → first forecast 2025-10-01
    expected_first = datetime(2025, 10, 1, tzinfo=timezone.utc)
    assert dts[0] == expected_first

    # Perf budget from your original test
    assert (time.time() - t0) <= 5.0


def test_forecast_daily_respects_public_horizon_and_dates(client, seeded_metric_daily):
    """
    Even if callers pass start/end, the public contract remains 7 rows.
    Dates remain UTC, increasing, and contiguous.
    """
    start = date(2025, 10, 1)
    end = start + timedelta(days=6)

    r = client.get(
        "/api/forecast/daily",
        params={
            "source_name": "demo-source",
            "metric": "value",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list) and len(data) == 7

    dts = [_parse_utc_z(row["metric_date"]) for row in data]
    assert dts[0] == datetime(2025, 10, 1, tzinfo=timezone.utc)
    assert all(dts[i] < dts[i + 1] for i in range(len(dts) - 1))
    assert all((dts[i + 1] - dts[i]) == timedelta(days=1) for i in range(len(dts) - 1))
