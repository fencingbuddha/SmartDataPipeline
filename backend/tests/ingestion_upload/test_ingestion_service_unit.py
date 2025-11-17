from __future__ import annotations

from datetime import datetime, timezone
import json

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text

from app.services import ingestion


def test_native_converts_supported_types():
    aware = pd.Timestamp("2024-01-02T03:04:05Z")
    naive = datetime(2024, 1, 2, 3, 4, 5)
    assert ingestion._native(aware) == aware.isoformat()
    naive_iso = ingestion._native(naive)
    assert naive_iso.endswith("+00:00")
    assert ingestion._native(np.int32(7)) == 7
    assert ingestion._native(np.float64(1.5)) == pytest.approx(1.5)
    assert ingestion._native(np.nan) is None
    assert ingestion._native("plain") == "plain"


def test_get_or_create_source_creates_and_reuses(db):
    created = ingestion._get_or_create_source(db, "unit-source")
    db.commit()
    fetched = ingestion._get_or_create_source(db, "unit-source")
    assert fetched.id == created.id
    assert db.execute(text("SELECT COUNT(*) FROM sources")).scalar_one() == 1


def test_iter_csv_bytes_skips_blank_lines():
    csv_bytes = b"name,value\nfoo,1\n,\nbar,2\n , \n"
    rows = list(ingestion.iter_csv_bytes(csv_bytes))
    assert rows == [{"name": "foo", "value": "1"}, {"name": "bar", "value": "2"}]


def test_iter_json_bytes_handles_array_and_ndjson():
    payload = json.dumps([{"value": 1}, {"value": 2}]).encode()
    assert list(ingestion.iter_json_bytes(payload)) == [{"value": 1}, {"value": 2}]

    ndjson = b'{"value":3}\n{"value": "bad"}\n{"not": "dict"}\n{"\n'
    parsed = list(ingestion.iter_json_bytes(ndjson))
    assert parsed[0] == {"value": 3}
    assert parsed[1] == {"value": "bad"}
    assert parsed[-1] == {"__parse_error__": '{"'}


def test_find_key_and_coercions():
    row = {"Time": "2024-01-01T00:00:00Z", "Amount": "5"}
    ts_key = ingestion._find_key(row, ingestion._TS_KEYS)
    num_key = ingestion._find_key(row, ingestion._VAL_KEYS)
    assert ts_key == "Time"
    assert num_key == "Amount"
    ts = ingestion._coerce_ts(row[ts_key])
    assert ts.tzinfo is not None
    assert ingestion._coerce_ts("not-a-ts") is None
    assert ingestion._coerce_num(row[num_key]) == pytest.approx(5.0)
    assert ingestion._coerce_num("nan") is None


def test_try_clean_row_validates_inputs():
    row = {"timestamp": "2024-01-01T00:00:00Z", "value": "3.5", "metric": "visits"}
    cleaned, warn = ingestion._try_clean_row(row, default_metric=None)
    assert warn is None
    assert cleaned["metric"] == "visits"

    missing_metric, warn = ingestion._try_clean_row({"timestamp": "2024-01-01", "value": 2}, default_metric="fallback")
    assert missing_metric["metric"] == "fallback"

    bad_ts, warn = ingestion._try_clean_row({"value": 1, "metric": "x"}, default_metric=None)
    assert bad_ts is None
    assert "timestamp" in warn

    parse_error, warn = ingestion._try_clean_row({"__parse_error__": "raw"}, default_metric=None)
    assert parse_error is None
    assert "JSON parse" in warn


def test_process_rows_tracks_stats_and_duplicates(db):
    rows = iter([
        {"timestamp": "2024-01-01T00:00:00Z", "metric": "events", "value": "10"},
        {"timestamp": "bad-ts", "metric": "events", "value": "8"},
        {"timestamp": "2024-01-01T00:00:00Z", "metric": "events", "value": "10"},
        {"timestamp": "2024-01-02T00:00:00Z", "value": 5},
        {"__parse_error__": '{"broken": true}'},
    ])

    stats = ingestion.process_rows(
        rows,
        source_name="pipeline",
        default_metric="fallback",
        db=db,
        filename="unit.csv",
        content_type="text/csv",
        batch_size=2,
    )

    assert stats["ingested_rows"] == 3
    assert stats["duplicates"] == 1
    assert stats["skipped_rows"] == 2
    assert stats["warnings"] and len(stats["warnings"]) == 2
    assert stats["metric"] == "events"
    assert stats["metrics"] == ["events", "fallback"]
    assert stats["min_ts"] == "2024-01-01T00:00:00+00:00"
    assert stats["max_ts"] == "2024-01-02T00:00:00+00:00"

    assert db.execute(text("SELECT COUNT(*) FROM raw_events")).scalar_one() == 5
    assert db.execute(text("SELECT COUNT(*) FROM clean_events")).scalar_one() == 2


def test_ingest_file_detects_json_payload(db):
    payload = json.dumps([{"timestamp": "2024-02-01T10:00:00Z", "value": 4}]).encode()
    stats = ingestion.ingest_file(
        db=db,
        source_name="json-source",
        file_bytes=payload,
        content_type="application/json",
        filename="data.json",
        default_metric="json_metric",
    )
    assert stats["ingested_rows"] == 1
    assert db.execute(text("SELECT COUNT(*) FROM raw_events")).scalar_one() == 1
    clean = db.execute(text("SELECT metric FROM clean_events")).scalar_one()
    assert clean == "json_metric"
