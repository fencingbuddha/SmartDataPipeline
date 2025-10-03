import time
from datetime import date, timedelta

def test_forecast_run_and_get(client, seeded_metric_daily):
    t0 = time.time()
    r = client.post("/api/forecast/run", params={
        "source_name":"demo-source","metric":"value","horizon_days":7
    })
    assert r.status_code == 200 and r.json()["inserted"] == 7
    start = date(2025,10,3); end = start + timedelta(days=7)
    r2 = client.get("/api/forecast/daily", params={
        "source_name":"demo-source","metric":"value",
        "start_date":start.isoformat(),"end_date":end.isoformat()
    })
    assert r2.status_code == 200 and len(r2.json()) == 7
    assert (time.time() - t0) <= 5.0
