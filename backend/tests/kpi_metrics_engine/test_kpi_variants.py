from __future__ import annotations

from datetime import date, timedelta, datetime
from typing import List, Dict

import sqlalchemy as sa
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def _mk_rows(start: date, per_day: List[int]) -> List[Dict]:
    """
    Build rows with UNIQUE timestamps per day to avoid the
    unique constraint on (source_id, ts, metric).
    """
    rows: List[Dict] = []
    for day_offset, n in enumerate(per_day):
        base_day = datetime.combine(start + timedelta(days=day_offset), datetime.min.time())
        for j in range(n):
            ts = (base_day + timedelta(minutes=j)).isoformat()  # 00:00, 00:01, 00:02, ...
            rows.append({"timestamp": ts, "metric": "events_total", "value": 1.0})
    return rows

def _ingest_and_run_kpi(source: str, rows: List[Dict], **extra):
    r = client.post(f"/api/ingest?source_name={source}", json=rows)
    assert r.status_code in (200, 201), r.text

    start_ts = rows[0]["timestamp"]
    end_ts   = rows[-1]["timestamp"]
    # Router wants dates, not datetimes
    start_date = start_ts.split("T")[0]
    end_date   = end_ts.split("T")[0]

    r2 = client.post(
        "/api/kpi/run",
        params={
            "source_name": source,
            "metric": "events_total",
            "start_date": start_date,
            "end_date": end_date,
            **extra,
        },
    )
    assert r2.status_code in (200, 201), r2.text

def test_kpi_agg_count_populates_value_count(db, reset_db):
    source = "count-demo"
    start = date(2025, 9, 1)
    # Day1: 3 rows, Day2: 2 rows
    rows = _mk_rows(start, per_day=[3, 2])
    _ingest_and_run_kpi(source, rows, agg="count")

    # Query metric_daily to assert counts landed
    res = db.execute(sa.text("""
        SELECT metric_date, value_count
        FROM metric_daily
        JOIN sources ON sources.id = metric_daily.source_id
        WHERE sources.name = :src AND metric = 'events_total'
        ORDER BY metric_date
    """), {"src": source}).fetchall()

    assert [int(r.value_count) for r in res] == [3, 2]

def test_kpi_distinct_id_sets_value_distinct(db, reset_db):
    source = "distinct-demo"
    start = date(2025, 9, 3)
    # Insert duplicates per day; distinct on 'id' should equal the count in this schema
    rows = _mk_rows(start, per_day=[4, 1])
    _ingest_and_run_kpi(source, rows, agg="sum", distinct_field="id")

    res = db.execute(sa.text("""
        SELECT metric_date, value_count, COALESCE(value_distinct, 0) AS vd
        FROM metric_daily
        JOIN sources ON sources.id = metric_daily.source_id
        WHERE sources.name = :src AND metric = 'events_total'
        ORDER BY metric_date
    """), {"src": source}).fetchall()

    counts = [int(r.value_count) for r in res]
    distincts = [int(r.vd) for r in res]
    # With distinct_field='id', value_distinct should match the per-day row count here
    assert counts == [4, 1]
    assert distincts == counts
