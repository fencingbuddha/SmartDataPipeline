from __future__ import annotations

from fastapi.testclient import TestClient
import sqlalchemy as sa

from app.main import app

client = TestClient(app)


def _unwrap_envelope(obj):
    """Return the API data payload regardless of envelope or legacy shape."""
    if isinstance(obj, dict) and "ok" in obj and "data" in obj:
        return obj["data"] or {}
    return obj


def _normalize_anomaly_response(out):
    """
    Accepts any of:
      • Enveloped: {"ok":..., "data": {"points":[...], ["anomalies":[...]]}, "meta": {...}}
      • New: {"points":[...], "anomalies":[...]}
      • Points-only: {"points":[...]}  (infer anomalies from is_outlier)
      • Legacy: [ {"date":..., "value":..., "is_outlier": bool}, ... ]
    Returns: (points_list, anomaly_dates_set)
    """
    out = _unwrap_envelope(out)

    # Dict with points [+/- anomalies]
    if isinstance(out, dict) and "points" in out:
        points = out.get("points", []) or []
        if "anomalies" in out and isinstance(out["anomalies"], list):
            anomaly_dates = {a.get("metric_date") for a in out["anomalies"] if a.get("metric_date")}
        else:
            anomaly_dates = {p.get("date") for p in points if isinstance(p, dict) and p.get("is_outlier")}
        return points, anomaly_dates

    # Legacy list of rows
    if isinstance(out, list):
        points = [{"metric_date": r.get("date"), "value": r.get("value")} for r in out if isinstance(r, dict)]
        anomaly_dates = {r.get("date") for r in out if isinstance(r, dict) and r.get("is_outlier")}
        return points, anomaly_dates

    raise AssertionError(f"Unexpected anomaly response shape: {type(out)} -> {out!r}")


def _seed_series_with_spike(db):
    """
    Seed a short series with one obvious spike on 2025-09-06.
    Uses value_sum/value_avg/value_count/value_distinct columns (no plain 'value').
    """
    # Ensure source exists (id = 401, name = 'demo')
    db.execute(sa.text("INSERT INTO sources (id, name) VALUES (401, 'demo') ON CONFLICT DO NOTHING"))

    rows = [
        ("2025-09-01", 10), ("2025-09-02", 11), ("2025-09-03", 9),
        ("2025-09-04", 10), ("2025-09-05", 10), ("2025-09-06", 100),  # spike
        ("2025-09-07", 10),
    ]

    for d, v in rows:
        db.execute(sa.text("""
            INSERT INTO metric_daily
                (metric_date, source_id, metric,
                 value_sum, value_avg, value_count, value_distinct)
            VALUES
                (:d, 401, 'events_total',
                 :v, :v, 1, NULL)
            ON CONFLICT (metric_date, source_id, metric)
            DO UPDATE SET
                value_sum = EXCLUDED.value_sum,
                value_avg = EXCLUDED.value_avg,
                value_count = EXCLUDED.value_count,
                value_distinct = EXCLUDED.value_distinct
        """), {"d": d, "v": float(v)})

    db.commit()


def test_anomaly_rolling_flags_spike(db, reset_db):
    _seed_series_with_spike(db)
    r = client.get(
        "/api/metrics/anomaly/rolling",
        params={
            "source_name": "demo",
            "metric": "events_total",
            "start_date": "2025-09-01",
            "end_date": "2025-09-08",
            "window": 3,
            "z_thresh": 3.0,
            "value_field": "value_sum",  # ignored by API, harmless
        },
    )
    assert r.status_code == 200, r.text
    points, anomaly_dates = _normalize_anomaly_response(r.json())
    # Expect at least the seeded 7 points, and the spike day flagged
    assert len(points) >= 7
    assert "2025-09-06" in anomaly_dates


def test_anomaly_empty_series_is_graceful(db, reset_db):
    r = client.get(
        "/api/metrics/anomaly/rolling",
        params={
            "source_name": "no-such-source",
            "metric": "events_total",
            "start_date": "2025-09-01",
            "end_date": "2025-09-08",
            "window": 3,
            "z_thresh": 3.0,
        },
    )

    # Two acceptable behaviors:
    # 1) 404 Not Found (either enveloped {ok:false,...} or FastAPI {"detail":...})
    # 2) 200 OK with an empty payload (enveloped points==[] or legacy [])
    if r.status_code == 404:
        data = r.json()
        if isinstance(data, dict) and "ok" in data and "data" in data:
            assert data["ok"] is False
            # error code may vary (UNKNOWN_SOURCE / NOT_FOUND)
            assert isinstance(data.get("error", {}), dict)
        else:
            assert "detail" in data
        return

    assert r.status_code == 200, r.text
    payload = _unwrap_envelope(r.json())
    if isinstance(payload, dict):
        assert payload.get("points", []) == []
        # anomalies may be omitted; treat as empty if missing
        assert payload.get("anomalies", []) in ([], None)
    else:
        # legacy list
        assert payload == []


def test_anomaly_bad_params_rejected(db, reset_db):
    r1 = client.get("/api/metrics/anomaly/rolling",
                    params={"source_name": "demo", "metric": "events_total", "window": 1, "z_thresh": 3.0})
    assert r1.status_code == 422
    r2 = client.get("/api/metrics/anomaly/rolling",
                    params={"source_name": "demo", "metric": "events_total", "window": 5, "z_thresh": -1.0})
    assert r2.status_code == 422
