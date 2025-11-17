from __future__ import annotations

from datetime import date

from sqlalchemy import text

from app.services import kpi


def _seed_source(db, name="kpi-source"):
    db.execute(text("INSERT INTO sources (name) VALUES (:name)"), {"name": name})
    db.commit()
    return db.execute(text("SELECT id FROM sources WHERE name = :name"), {"name": name}).scalar_one()


def _insert_event(db, source_id, ts, metric, value):
    db.execute(
        text(
            """
            INSERT INTO clean_events (source_id, ts, metric, value, flags)
            VALUES (:source_id, :ts, :metric, :value, '{}')
            """
        ),
        {"source_id": source_id, "ts": ts, "metric": metric, "value": value},
    )
    db.commit()


def test_run_daily_kpis_aggregates_and_upserts(db):
    source_id = _seed_source(db)
    _insert_event(db, source_id, "2024-01-01T00:00:00Z", "visits", 5)
    _insert_event(db, source_id, "2024-01-01T12:00:00Z", "visits", 7)
    _insert_event(db, source_id, "2024-01-02T00:00:00Z", "visits", 3)
    _insert_event(db, source_id, "2024-01-02T01:00:00Z", "errors", 1)

    upserted, preview = kpi.run_daily_kpis(db, source_id=source_id, distinct_field="metric")
    assert upserted == 3
    days = {row["metric_date"] for row in preview}
    assert days == {"2024-01-01", "2024-01-02"}

    rows = db.execute(
        text(
            """
            SELECT metric_date, metric, value_sum, value_count, value_distinct
            FROM metric_daily
            WHERE source_id = :sid
            ORDER BY metric_date, metric
            """
        ),
        {"sid": source_id},
    ).fetchall()
    assert rows[0][2:] == (12.0, 2, 1)

    # Add another event on the same day to ensure existing rows are updated
    _insert_event(db, source_id, "2024-01-01T18:00:00Z", "visits", 2)
    upserted_again, _ = kpi.run_daily_kpis(db, source_id=source_id, metric_name="visits")
    assert upserted_again == 2
    updated = db.execute(
        text(
            "SELECT value_sum, value_count FROM metric_daily WHERE source_id = :sid AND metric = 'visits' AND metric_date = '2024-01-01'"
        ),
        {"sid": source_id},
    ).one()
    assert updated == (14.0, 3)


def test_run_daily_kpis_swaps_inverted_range(db):
    source_id = _seed_source(db, name="range-source")
    _insert_event(db, source_id, "2024-02-01T00:00:00Z", "visits", 1)
    count, preview = kpi.run_daily_kpis(
        db,
        start=date(2024, 2, 3),
        end=date(2024, 1, 31),
        source_id=source_id,
        metric_name="visits",
    )
    assert count == 1
    assert preview[0]["metric_date"] == "2024-02-01"


def test_run_daily_kpis_returns_zero_when_no_events(db):
    source_id = _seed_source(db, name="empty-source")
    count, preview = kpi.run_daily_kpis(
        db,
        source_id=source_id,
        metric_name="missing",
    )
    assert count == 0
    assert preview == []


def test_run_kpi_for_metric_handles_missing_source(db):
    result = kpi.run_kpi_for_metric(db, source_name="nope", metric="visits")
    assert result["upserted"] == 0
    assert "not found" in result["message"]


def test_run_kpi_for_metric_auto_window_and_preview(db):
    source_id = _seed_source(db, name="auto-source")
    _insert_event(db, source_id, "2024-03-01T00:00:00Z", "visits", 4)
    _insert_event(db, source_id, "2024-03-02T00:00:00Z", "visits", 6)

    result = kpi.run_kpi_for_metric(db, source_name="auto-source", metric="visits", distinct_field="metric")
    assert result["upserted"] == 2
    assert result["start"] == "2024-03-01"
    assert result["end"] == "2024-03-02"
    assert len(result["preview"]) == 2
