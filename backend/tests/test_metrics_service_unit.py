from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import text

from app.services import metrics


def _seed_metrics(db, source_name="alpha"):
    db.execute(text("INSERT INTO sources (name) VALUES (:name)"), {"name": source_name})
    db.commit()
    source_id = db.execute(text("SELECT id FROM sources WHERE name = :name"), {"name": source_name}).scalar_one()

    base = date(2024, 1, 1)
    rows = []
    for i in range(5):
        rows.append(
            {
                "metric_date": (base + timedelta(days=i)).isoformat(),
                "source_id": source_id,
                "metric": "visits" if i % 2 == 0 else "errors",
                "value_sum": 10 + i,
                "value_avg": 5 + i,
                "value_count": 2 + i,
                "value_distinct": 1,
            }
        )
    db.execute(
        text(
            """
            INSERT INTO metric_daily (metric_date, source_id, metric, value_sum, value_avg, value_count, value_distinct)
            VALUES (:metric_date, :source_id, :metric, :value_sum, :value_avg, :value_count, :value_distinct)
            """
        ),
        rows,
    )
    db.commit()
    return source_id


def test_fetch_metric_daily_supports_optional_metric_and_order(db):
    source_id = _seed_metrics(db)
    rows = metrics.fetch_metric_daily(db, source_id=source_id, metric=None, order="desc", limit=3)
    assert len(rows) == 3
    assert rows[0].metric_date > rows[-1].metric_date
    assert {r.metric for r in rows} <= {"visits", "errors"}


def test_fetch_metric_daily_as_dicts_and_attribute_access(db):
    source_id = _seed_metrics(db, source_name="beta")
    rows = metrics.fetch_metric_daily(db, source_id=source_id, metric="visits")
    first = rows[0]
    assert first.metric == "visits"
    assert first.to_dict()["metric"] == "visits"

    as_dicts = metrics.fetch_metric_daily_as_dicts(db, source_id=source_id, metric="visits")
    assert as_dicts and as_dicts[0]["metric"] == "visits"


def test_fetch_metric_names_filters_by_source(db):
    source_id_a = _seed_metrics(db, source_name="gamma")
    source_id_b = _seed_metrics(db, source_name="delta")
    names_all = metrics.fetch_metric_names(db)
    assert "visits" in names_all and "errors" in names_all
    names_gamma = metrics.fetch_metric_names(db, source_name="gamma")
    assert names_gamma == ["errors", "visits"]


def test_to_csv_handles_row_and_dict(db):
    source_id = _seed_metrics(db, source_name="epsilon")
    row = metrics.fetch_metric_daily(db, source_id=source_id, metric="visits", limit=1)[0]
    csv_text = metrics.to_csv([row, row.to_dict()])
    lines = csv_text.splitlines()
    assert lines[0].startswith("metric_date")
    assert len(lines) == 3
