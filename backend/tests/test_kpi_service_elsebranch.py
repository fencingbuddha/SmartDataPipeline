from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sqlalchemy as sa
import pytest

from app.services.kpi import run_daily_kpis
from app.models import CleanEvent


def _make_source(db, name="else-demo") -> int:
    sid = db.execute(sa.text("INSERT INTO sources (name) VALUES (:n) RETURNING id"), {"n": name}).scalar()
    db.commit()
    return sid


def _seed_events_else_branch(db, sid: int):
    # Two days of data, tz-aware timestamps to satisfy astimezone() in service
    base = datetime(2025, 9, 10, 0, 0, 0, tzinfo=timezone.utc)
    rows = [
        (base + timedelta(minutes=0), sid, "events_total", 1.0),             # day 1: sum=1, count=1
        (base + timedelta(days=1, minutes=0), sid, "events_total", 2.0),     # day 2: 2 + 3 = 5, count=2
        (base + timedelta(days=1, minutes=5), sid, "events_total", 3.0),
    ]
    for ts, s, metric, val in rows:
        db.add(CleanEvent(ts=ts, source_id=s, metric=metric, value=val))
    db.commit()


def test_kpi_service_else_branch_upserts_python_path(db, reset_db, monkeypatch):
    sid = _make_source(db)
    _seed_events_else_branch(db, sid)

    # Force the non-PostgreSQL path by overriding the dialect name on the existing engine
    original_name = getattr(db.bind.dialect, "name", "postgresql")
    monkeypatch.setattr(db.bind.dialect, "name", "sqlite", raising=False)

    try:
        upserted, preview = run_daily_kpis(
            db,
            start=None,
            end=None,
            metric_name="events_total",
            source_id=sid,
        )
        assert upserted == 2
        assert isinstance(preview, list) and len(preview) == 2

        # Verify rows in metric_daily
        res = db.execute(sa.text("""
            SELECT metric_date, value_sum, value_avg, value_count
            FROM metric_daily
            WHERE source_id = :sid AND metric = 'events_total'
            ORDER BY metric_date
        """), {"sid": sid}).fetchall()

        assert len(res) == 2
        # Day 1: sum 1.0, count 1, avg 1.0
        assert float(res[0].value_sum) == pytest.approx(1.0)
        assert int(res[0].value_count) == 1
        # Day 2: sum 5.0, count 2, avg 2.5
        assert float(res[1].value_sum) == pytest.approx(5.0)
        assert int(res[1].value_count) == 2
    finally:
        # not strictly necessary with monkeypatch, but safe if reused
        monkeypatch.setattr(db.bind.dialect, "name", original_name, raising=False)
