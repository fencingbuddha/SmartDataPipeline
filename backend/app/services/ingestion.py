from __future__ import annotations

from typing import Iterable, Dict, Any, Optional, List, Tuple, Set
from datetime import datetime, timezone
import io, csv, json

import numpy as np
import pandas as pd
import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from app.models import Source, RawEvent, CleanEvent

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _native(v: Any):
    """Convert pandas/numpy/datetime values into JSON-safe Python types."""
    if isinstance(v, (pd.Timestamp, datetime)):
        if isinstance(v, pd.Timestamp):
            v = v.tz_convert("UTC") if v.tzinfo else v.tz_localize("UTC")
            return v.to_pydatetime().astimezone(timezone.utc).isoformat()
        return v.astimezone(timezone.utc).isoformat()
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if pd.isna(v):
        return None
    return v


def _get_or_create_source(db: Session, source_name: str) -> Source:
    src = db.execute(select(Source).where(Source.name == source_name)).scalar_one_or_none()
    if src:
        return src
    src = Source(name=source_name)
    db.add(src)
    db.flush()  # so src.id is available
    return src


# ---------------------------------------------------------------------------
# Flexible parsers (bytes -> row dicts). Use these for /api/ingest if needed.
# ---------------------------------------------------------------------------

def iter_csv_bytes(file_bytes: bytes) -> Iterable[Dict[str, Any]]:
    """Yield dictionaries from CSV bytes (UTF-8/BOM tolerant)."""
    text = file_bytes.decode("utf-8-sig", errors="replace")
    f = io.StringIO(text)
    reader = csv.DictReader(f)
    for row in reader:
        # skip completely blank lines
        if not any((str(v or "").strip() for v in row.values())):
            continue
        yield row


def iter_json_bytes(file_bytes: bytes) -> Iterable[Dict[str, Any]]:
    """
    Yield dictionaries from JSON bytes.
    Supports:
      - JSON array: [ {...}, {...} ]
      - NDJSON: one JSON object per line
    """
    s = file_bytes.decode("utf-8-sig", errors="replace").strip()
    if not s:
        return
    # Try JSON array first
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            yield obj
            return
        if isinstance(obj, list):
            for item in obj:
                if isinstance(item, dict):
                    yield item
            return
    except Exception as exc:
        logger.warning("iter_json_bytes.array_parse_failed", error=str(exc))
    # Fallback to NDJSON
    for ln in s.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            item = json.loads(ln)
            if isinstance(item, dict):
                yield item
        except Exception:
            # surface bad lines as parse errors for stats
            yield {"__parse_error__": ln}


# ---------------------------------------------------------------------------
# Row cleaning (tolerant)
# ---------------------------------------------------------------------------

_TS_KEYS = {"timestamp", "time", "date", "datetime"}
_VAL_KEYS = {"value", "amount", "count", "qty", "quantity"}
_METRIC_KEYS = {"metric", "name", "metric_name"}


def _find_key(d: Dict[str, Any], pool: set[str]) -> Optional[str]:
    for k in d.keys():
        if k and k.lower() in pool:
            return k
    return None


def _coerce_ts(v: Any) -> Optional[datetime]:
    try:
        ts = pd.to_datetime(v, errors="coerce", utc=True)
        if pd.isna(ts):
            return None
        return ts.to_pydatetime() if isinstance(ts, pd.Timestamp) else ts
    except Exception:
        return None


def _coerce_num(v: Any) -> Optional[float]:
    try:
        num = pd.to_numeric(v, errors="coerce")
        if pd.isna(num):
            return None
        return float(num)
    except Exception:
        return None


def _try_clean_row(row: Dict[str, Any], default_metric: Optional[str]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Return (clean_row | None, warning | None).
    clean_row fields: ts (aware UTC), metric (str), value (float)
    """
    if row is None:
        return None, "Empty row"

    # Handle JSON parse errors surfaced by iter_json_bytes
    if "__parse_error__" in row:
        return None, "JSON parse error in NDJSON line"

    ts_key = _find_key(row, _TS_KEYS)
    val_key = _find_key(row, _VAL_KEYS)
    met_key = _find_key(row, _METRIC_KEYS)

    ts = _coerce_ts(row.get(ts_key)) if ts_key else None
    val = _coerce_num(row.get(val_key)) if val_key else None
    metric = (str(row.get(met_key)).strip() if met_key and row.get(met_key) not in (None, "") else None) or default_metric

    if ts is None:
        return None, f"Invalid/missing timestamp ({ts_key or 'timestamp'})"
    if val is None:
        return None, f"Invalid/missing numeric value ({val_key or 'value'})"
    if not metric:
        return None, "Missing metric and no default_metric provided"

    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    return {"ts": ts, "metric": metric, "value": float(val)}, None


# ---------------------------------------------------------------------------
# Main processor used by /api/upload and /api/ingest
# ---------------------------------------------------------------------------

def process_rows(
    rows_iter: Iterable[Dict[str, Any]],
    *,
    source_name: str,
    default_metric: Optional[str],
    db: Session,
    filename: Optional[str] = None,
    content_type: Optional[str] = None,
    batch_size: int = 1000,
) -> Dict[str, Any]:
    """
    Stream rows, tolerate bad lines, and upsert into CleanEvent.
    Also records RawEvent for each parsed row.
    Returns stats suitable for the UI.
    """
    warnings: List[str] = []
    raw_buffer: List[RawEvent] = []
    clean_buffer: List[Dict[str, Any]] = []

    ingested_rows = 0     # valid -> CleanEvent upsert attempts
    skipped_rows = 0      # invalid rows
    duplicates_total = 0  # upsert "do nothing" counts
    min_ts: Optional[datetime] = None
    max_ts: Optional[datetime] = None
    metrics_seen: Set[str] = set()
    metric_first: Optional[str] = None
    now_utc = datetime.now(timezone.utc)

    # Start a transaction; if one already exists, start a nested (SAVEPOINT) txn.
    trans_ctx = db.begin_nested() if db.in_transaction() else db.begin()
    with trans_ctx:
        src = _get_or_create_source(db, source_name)

        def flush_raw():
            nonlocal raw_buffer
            if raw_buffer:
                db.add_all(raw_buffer)
                raw_buffer = []

        def flush_clean():
            nonlocal clean_buffer, duplicates_total
            if not clean_buffer:
                return
            # ensure source_id set
            for rc in clean_buffer:
                rc["source_id"] = src.id
            stmt = insert(CleanEvent).values(clean_buffer).on_conflict_do_nothing(
                index_elements=["source_id", "ts", "metric"]
            )
            result = db.execute(stmt)
            inserted = int(result.rowcount or 0)
            duplicates_total += max(len(clean_buffer) - inserted, 0)
            clean_buffer = []

        for raw in rows_iter:
            # Always log raw rows (even invalid) for traceability
            payload = {k: _native(v) for k, v in (raw or {}).items()}
            raw_buffer.append(RawEvent(
                source_id=src.id,
                filename=filename,
                content_type=content_type,
                payload=payload,
                received_at=now_utc,
            ))
            if len(raw_buffer) >= batch_size:
                flush_raw()

            # Clean + validate
            clean, warn = _try_clean_row(raw, default_metric=default_metric)
            if warn:
                skipped_rows += 1
                if len(warnings) < 50:  # cap warnings to avoid huge responses
                    warnings.append(warn)
                continue

            # Track min/max + all metrics
            ts = clean["ts"]
            if min_ts is None or ts < min_ts:
                min_ts = ts
            if max_ts is None or ts > max_ts:
                max_ts = ts
            m = clean["metric"]
            if not metric_first:
                metric_first = m
            metrics_seen.add(m)

            clean_buffer.append({
                "source_id": None,  # set in flush_clean
                "ts": ts,
                "metric": m,
                "value": clean["value"],
            })
            ingested_rows += 1

            if len(clean_buffer) >= batch_size:
                flush_clean()

        # final flush
        flush_raw()
        flush_clean()

    metrics_list = sorted(metrics_seen) if metrics_seen else []
    return {
        "ingested_rows": ingested_rows,
        "skipped_rows": skipped_rows,
        "duplicates": duplicates_total,
        "warnings": warnings,
        "metric": metric_first,           # back-compat (first seen)
        "metrics": metrics_list,          # all metrics seen
        "min_ts": min_ts.isoformat() if min_ts else None,
        "max_ts": max_ts.isoformat() if max_ts else None,
    }


# ---------------------------------------------------------------------------
# Convenience: bytes -> rows_iter -> process_rows
# Useful for /api/ingest (raw body) or legacy callers.
# ---------------------------------------------------------------------------

def ingest_file(
    db: Session,
    source_name: str,
    file_bytes: bytes,
    content_type: str,
    filename: Optional[str] = None,
    default_metric: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Detect CSV vs JSON/NDJSON from content_type and ingest using process_rows.
    Returns the same stats dict as process_rows.
    """
    is_json = "json" in (content_type or "").lower()
    rows_iter = iter_json_bytes(file_bytes) if is_json else iter_csv_bytes(file_bytes)
    return process_rows(
        rows_iter,
        source_name=source_name,
        default_metric=default_metric,
        db=db,
        filename=filename,
        content_type=content_type,
    )
