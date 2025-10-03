from datetime import date, timedelta
import time

def test_forecast_run_and_get(client, seeded_metric_daily):
    t0 = time.time()
    r = client.post("/api/forecast/run", params={
        "source_name":"demo-source","metric":"value","horizon_days":7
    })
    assert r.status_code == 200 and r.json()["inserted"] == 7

    # Last observed = 2025-09-30 (from fixture), so forecast starts 2025-10-01
    start = date(2025, 10, 1)
    end = start + timedelta(days=6)  # through 2025-10-07 (7 days)

    r2 = client.get("/api/forecast/daily", params={
        "source_name":"demo-source","metric":"value",
        "start_date": start.isoformat(), "end_date": end.isoformat()
    })
    data = r2.json()
    assert r2.status_code == 200 and len(data) == 7
    assert (time.time() - t0) <= 5.0
