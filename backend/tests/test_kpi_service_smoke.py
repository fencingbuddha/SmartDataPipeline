from datetime import datetime, timezone, date
from app.models import Source, CleanEvent
from app.services.kpi import run_daily_kpis

def test_run_daily_kpis_upserts(db, reset_db):
    # Arrange: a source + two clean events on the same day
    src = Source(name="demo")
    db.add(src); db.flush()

    db.add_all([
        CleanEvent(
            source_id=src.id,
            ts=datetime(2025, 9, 16, 10, 0, 0, tzinfo=timezone.utc),
            metric="events_total",
            value=5,
        ),
        CleanEvent(
            source_id=src.id,
            ts=datetime(2025, 9, 16, 12, 0, 0, tzinfo=timezone.utc),
            metric="events_total",
            value=7,
        ),
    ])
    db.commit()

    # Act
    upserted, preview = run_daily_kpis(
        db,
        start=date(2025, 9, 16),
        end=date(2025, 9, 16),
        metric_name="events_total",
    )

    # Assert: 1 day aggregated, sum is 12
    assert upserted == 1
    assert preview and preview[0]["value_sum"] == 12
