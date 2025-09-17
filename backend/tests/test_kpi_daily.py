from datetime import date
import sqlalchemy as sa
from app.services.kpi import run_daily_kpis

def test_daily_kpis_upsert_and_idempotent(db, reset_db):
    # seed a source to satisfy FKs
    db.execute(sa.text("INSERT INTO sources (id, name) VALUES (101, 'demo') ON CONFLICT DO NOTHING"))

    # seed four clean events across two days
    rows = [
        (101, "2025-09-05T10:00:00+00:00", "default", 10.0),
        (101, "2025-09-05T11:00:00+00:00", "default", 15.0),
        (101, "2025-09-06T09:30:00+00:00", "default",  8.5),
        (101, "2025-09-06T10:05:00+00:00", "default",  6.0),
    ]
    db.execute(
        sa.text(
            "INSERT INTO clean_events (source_id, ts, metric, value) "
            "VALUES (:sid, :ts, :metric, :val)"
        ),
        [{"sid": sid, "ts": ts, "metric": m, "val": val} for sid, ts, m, val in rows],
    )
    db.commit()

    # run KPI for the full window
    upserted, preview = run_daily_kpis(
        db,
        start=date(2025, 9, 1),
        end=date(2025, 9, 17),
        metric_name="default",
    )
    assert upserted == 2
    assert preview == [
        {"metric_date": "2025-09-05", "source_id": 101, "metric": "default", "value_count": 2, "value_sum": 25.0, "value_avg": 12.5},
        {"metric_date": "2025-09-06", "source_id": 101, "metric": "default", "value_count": 2, "value_sum": 14.5, "value_avg": 7.25},
    ]

    # idempotency: second run overwrites the same 2 rows
    upserted2, _ = run_daily_kpis(
        db,
        start=date(2025, 9, 1),
        end=date(2025, 9, 17),
        metric_name="default",
    )
    assert upserted2 == 2

    # verify persisted rows
    res = db.execute(sa.text("""
        SELECT metric_date::text, source_id, metric, value_count, value_sum::float, value_avg::float
        FROM metric_daily
        ORDER BY metric_date, source_id, metric
    """)).all()
    assert res == [
        ("2025-09-05", 101, "default", 2, 25.0, 12.5),
        ("2025-09-06", 101, "default", 2, 14.5, 7.25),
    ]
