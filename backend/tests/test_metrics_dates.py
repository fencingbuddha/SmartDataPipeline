from __future__ import annotations


def test_daily_date_range(client, seeded_metric_daily):
    start = seeded_metric_daily["start_date"].isoformat()
    end = seeded_metric_daily["end_date"].isoformat()

    resp = client.get(
        "/api/metrics/daily",
        params={
            "source_name": seeded_metric_daily["source_name"],
            "metric": seeded_metric_daily["metric"],
            "start_date": start,
            "end_date": end,
        },
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["meta"]["params"]["start_date"] == start

    data = payload["data"]
    assert data, "expected seeded data in response"
    assert data[0]["metric_date"] >= start
    assert data[-1]["metric_date"] <= end
