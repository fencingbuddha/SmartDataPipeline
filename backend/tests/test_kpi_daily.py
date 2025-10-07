from __future__ import annotations

from datetime import date
import sqlalchemy as sa

from app.services.kpi import run_daily_kpis


def _call_run_daily_kpis(db, start, end, metric_name: str):
    """
    Be tolerant of minor API differences:
      - param names: (start, end) vs (start_date, end_date)
      - metric arg name: metric_name vs metric
      - return shape: (rows_upserted, preview) OR {"rows_upserted":..., "preview":[...]}.
    """
    # Try common kwarg patterns
    try:
        result = run_daily_kpis(db, start=start, end=end, metric_name=metric_name)
    except TypeError:
        try:
            result = run_daily_kpis(db, start_date=start, end_date=end, metric=metric_name)
        except TypeError:
            # last resort: positional
            result = run_daily_kpis(db, start, end, metric_name)

    # Normalize return
    if isinstance(result, tuple) and len(result) == 2:
        rows_upserted, preview = result
    elif isinstance(result, dict):
        rows_upserted = (
            result.get("rows_upserted")
            if "rows_upserted" in result
            else result.get("upserted")
        )
        preview = result.get("preview") or result.get("rows") or []
    else:
        raise AssertionError(f"Unexpected return from run_daily_kpis: {type(result)} -> {result!r}")

    return int(rows_upserted), list(preview)


def _normalize_preview(preview):
    """
    Keep only fields we assert on, and normalize types:
      - metric_date -> 'YYYY-MM-DD' string
      - value_sum / value_avg to float
      - value_count to int
    """
    out = []
    for r in preview:
        md = r.get("metric_date")
        # handle date, datetime, or str
        if hasattr(md, "isoformat"):
            md = md.isoformat()
        if isinstance(md, str) and "T" in md:
            md = md.split("T", 1)[0]

        out.append({
            "metric_date": md,
            "source_id": int(r.get("source_id")),
            "metric": r.get("metric"),
            "value_count": int(r.get("value_count")),
            "value_sum": float(r.get("value_sum")),
            "value_avg": float(r.get("value_avg")),
        })
    # deterministic order
    out.sort(key=lambda x: (x["metric"], x["source_id"], x["metric_date"]))
    return out


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
    upserted, preview = _call_run_daily_kpis(
        db,
        start=date(2025, 9, 1),
        end=date(2025, 9, 17),
        metric_name="default",
    )
    assert upserted == 2

    norm_preview = _normalize_preview(preview)
    assert norm_preview == [
        {"metric_date": "2025-09-05", "source_id": 101, "metric": "default", "value_count": 2, "value_sum": 25.0, "value_avg": 12.5},
        {"metric_date": "2025-09-06", "source_id": 101, "metric": "default", "value_count": 2, "value_sum": 14.5, "value_avg": 7.25},
    ]

    # idempotency: second run overwrites the same 2 rows
    upserted2, _ = _call_run_daily_kpis(
        db,
        start=date(2025, 9, 1),
        end=date(2025, 9, 17),
        metric_name="default",
    )
    assert upserted2 == 2

    # verify persisted rows (normalize SQL result types)
    res = db.execute(sa.text("""
        SELECT metric_date::text, source_id, metric, value_count, value_sum::float, value_avg::float
        FROM metric_daily
        ORDER BY metric_date, source_id, metric
    """)).all()

    # Coerce result row types to match our expected literals
    res_norm = [(str(d), int(sid), m, int(vc), float(vs), float(va))
                for (d, sid, m, vc, vs, va) in res]

    assert res_norm == [
        ("2025-09-05", 101, "default", 2, 25.0, 12.5),
        ("2025-09-06", 101, "default", 2, 14.5, 7.25),
    ]
