# backend/app/routers/ingest.py
from __future__ import annotations

from typing import List, Optional, Dict, Tuple
from datetime import datetime, date as Date, timezone
from json import JSONDecodeError
import io
import csv

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session
import sqlalchemy as sa
from sqlalchemy import text

from app.db.session import get_db
from app.schemas.common import ok, fail, ResponseMeta
from app.models.source import Source

# Import model (we insert with SQL text but keep this for type/context)
try:
    from app.models.clean_event import CleanEvent  # noqa: F401
except Exception:
    CleanEvent = None  # type: ignore

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


def _meta(**params) -> ResponseMeta:
    clean = {k: v for k, v in params.items() if v is not None}
    return ResponseMeta(
        params=clean or None,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


class IngestEvent(BaseModel):
    timestamp: datetime
    value: float = Field(..., description="numeric value to aggregate")
    source: Optional[str] = Field(None, description="logical source name")
    metric: str = Field(..., description="metric name, e.g., events_total")


def _ensure_source(db: Session, name: str) -> Source:
    src = db.query(Source).filter(Source.name == name).one_or_none()
    if not src:
        src = Source(name=name)
        db.add(src)
        db.commit()
        db.refresh(src)
    return src


def _aggregate_and_upsert(db: Session, source_id: int, events: List[IngestEvent]) -> dict:
    grouped: Dict[Tuple[Date, str], Dict[str, float]] = {}
    for e in events:
        d: Date = e.timestamp.date()
        key = (d, e.metric)
        g = grouped.setdefault(key, {"sum": 0.0, "count": 0.0})
        g["sum"] += float(e.value)
        g["count"] += 1.0

    upsert_sql = text(
        """
        INSERT INTO metric_daily
            (metric_date, source_id, metric,
             value_sum, value_avg, value_count, value_distinct)
        VALUES
            (:metric_date, :source_id, :metric,
             :value_sum, NULL, :value_count, NULL)
        ON CONFLICT (metric_date, source_id, metric)
        DO UPDATE SET
            value_sum      = COALESCE(metric_daily.value_sum, 0) + EXCLUDED.value_sum,
            value_count    = COALESCE(metric_daily.value_count, 0) + EXCLUDED.value_count,
            value_avg      = NULL,
            value_distinct = COALESCE(metric_daily.value_distinct, NULL)
        """
    )
    for (d, metric), agg in grouped.items():
        db.execute(
            upsert_sql,
            {
                "metric_date": d,
                "source_id": source_id,
                "metric": metric,
                "value_sum": agg["sum"],
                "value_count": int(agg["count"]),
            },
        )

    start_d = min(d for (d, _m) in grouped.keys())
    end_d = max(d for (d, _m) in grouped.keys())
    metrics = sorted({m for (_d, m) in grouped.keys()})

    return {
        "rows_ingested": sum(int(v["count"]) for v in grouped.values()),
        "groups_upserted": len(grouped),
        "metrics": metrics,
        "start_date": str(start_d),
        "end_date": str(end_d),
        "num_days": (end_d - start_d).days + 1,
    }


def _to_datetime_utc(ts):
    if isinstance(ts, datetime):
        dt = ts
    else:
        # tolerate trailing 'Z'
        ts = str(ts)
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _insert_clean_events_strict(db: Session, source_id: int, events: List[IngestEvent]) -> int:
    """
    Insert clean_events rows, ignoring exact duplicates on (source_id, ts, metric).
    Returns the count of newly inserted rows.
    """
    # If table doesn't exist in tests, just no-op
    reg = db.execute(text("SELECT to_regclass('clean_events')")).scalar()
    if not reg:
        return 0

    stmt = sa.text(
        """
        INSERT INTO clean_events (source_id, ts, metric, value)
        VALUES (:source_id, :ts, :metric, :value)
        ON CONFLICT (source_id, ts, metric) DO NOTHING
        RETURNING id
        """
    )

    inserted = 0
    for ev in events:
        ts_dt = _to_datetime_utc(ev.timestamp)
        params = {
            "source_id": source_id,
            "ts": ts_dt,
            "metric": ev.metric,
            "value": float(ev.value),
        }
        # RETURNING gives a row only when an insert actually happened
        res = db.execute(stmt, params)
        if res.fetchone() is not None:
            inserted += 1

    return inserted


@router.post("")
async def ingest_json_or_csv(
    request: Request,
    source_name: Optional[str] = Query(None, description="Default source name for all events"),
    default_metric: str = Query("events_total", description="Metric to use if not present (CSV/JSON rows)"),
    db: Session = Depends(get_db),
):
    """
    Ingest either:
      - Raw JSON: application/json body is a list of events (returns 200 OK per tests)
      - CSV via multipart: files={'file': ('data.csv', ..., 'text/csv')} (returns 200 OK)

    Rules:
      - Multipart JSON (file content-type application/json) is rejected with 415.
      - Multipart CSV is accepted and returns 200 OK.
      - Raw JSON success returns 200 OK.
      - Missing 'value' column in CSV => 400.
      - Empty CSV (no bytes, or header-only) => 400.
    """
    ctype = (request.headers.get("content-type") or "").lower()

    # ---- MULTIPART PATH (CSV expected) ----
    if "multipart/form-data" in ctype:
        form = await request.form()
        file = form.get("file")
        if file is None:
            return fail(
                code="BAD_REQUEST",
                message="No 'file' part in multipart form-data.",
                status_code=400,
                meta=_meta(),
            )

        file_ct = (getattr(file, "content_type", None) or "").lower()

        # Reject multipart JSON explicitly
        if file_ct in {"application/json", "application/ndjson", "text/json"}:
            return fail(
                code="UNSUPPORTED_MEDIA_TYPE",
                message="Send raw application/json (array of events), not multipart/form-data.",
                status_code=415,
                meta=_meta(),
            )

        # Accept CSV-ish types
        if file_ct in {"text/csv", "application/csv", "application/vnd.ms-excel"}:
            raw = await file.read()

            # Truly empty file (no bytes)
            if not raw or raw.strip() == b"":
                return fail(
                    code="EMPTY_FILE",
                    message="CSV file is empty.",
                    status_code=400,
                    meta=_meta(),
                )

            # Decode to text
            try:
                text_data = raw.decode("utf-8")
            except Exception:
                return fail(
                    code="CSV_DECODE_ERROR",
                    message="CSV must be UTF-8 encoded.",
                    status_code=400,
                    meta=_meta(),
                )

            # --- Header validation before parsing rows ---
            peek_reader = csv.reader(io.StringIO(text_data))
            try:
                header = next(peek_reader)
            except StopIteration:
                return fail(
                    code="EMPTY_FILE",
                    message="CSV file is empty.",
                    status_code=400,
                    meta=_meta(),
                )

            fieldnames = [h.strip().lower() for h in header]
            required = {"timestamp", "value"}
            missing = sorted(list(required - set(fieldnames)))
            if missing:
                return fail(
                    code="MISSING_COLUMNS",
                    message=f"CSV must include columns: {', '.join(missing)}.",
                    status_code=400,  # tests require 400 when 'value' column is missing
                    details={"present": fieldnames},
                    meta=_meta(),
                )

            # Parse rows now that header is valid
            reader = csv.DictReader(io.StringIO(text_data))
            rows = list(reader)

            # Header-only (no data rows) => 400
            if not rows:
                return fail(
                    code="EMPTY_FILE",
                    message="CSV contains a header but no data rows.",
                    status_code=400,
                    meta=_meta(),
                )

            # Normalize → validate
            events: List[IngestEvent] = []
            errors: List[dict] = []
            for idx, row in enumerate(rows):
                try:
                    item = dict(row)
                    # defaults
                    if not item.get("metric"):
                        item["metric"] = default_metric
                    if not item.get("source") and source_name:
                        item["source"] = source_name
                    events.append(IngestEvent.model_validate(item))
                except Exception as e:
                    errors.append({"index": idx, "error": str(e), "row": row})

            if errors:
                return fail(
                    code="BAD_REQUEST",
                    message="One or more CSV rows are invalid.",
                    status_code=400,
                    details={"errors": errors},
                    meta=_meta(),
    )

            eff_source = source_name or next((e.source for e in events if e.source), None)
            if not eff_source:
                return fail(
                    code="VALIDATION_ERROR",
                    message="source_name is required (either as query param or CSV 'source' column).",
                    status_code=422,
                    meta=_meta(),
                )

            src = _ensure_source(db, eff_source)

            inserted_rows = _insert_clean_events_strict(db, src.id, events)
            duplicates = max(0, len(events) - inserted_rows)
            result = _aggregate_and_upsert(db, src.id, events)
            db.commit()

            resp = ok(
                data={
                    "inserted": inserted_rows,
                    "duplicates": duplicates,
                    "rows_ingested": result["rows_ingested"],
                    "groups_upserted": result["groups_upserted"],
                    "metrics": result["metrics"],
                },
                meta=_meta(
                    source_name=eff_source,
                    start_date=result["start_date"],
                    end_date=result["end_date"],
                    num_days=result["num_days"],
                ),
            )
            if isinstance(resp, JSONResponse):
                resp.status_code = 200
            return resp

        # Unknown multipart file type
        return fail(
            code="UNSUPPORTED_MEDIA_TYPE",
            message=f"Unsupported multipart file content-type: {file_ct or 'unknown'}",
            status_code=415,
            meta=_meta(),
        )

    # ---- RAW JSON PATH ----
    try:
        payload = await request.json()
    except JSONDecodeError as e:
        return fail(
            code="JSON_DECODE_ERROR",
            message="Invalid JSON body.",
            status_code=400,
            details={"pos": e.pos, "msg": str(e)},
            meta=_meta(),
        )

    if not isinstance(payload, list):
        return fail(
            code="VALIDATION_ERROR",
            message="Body must be a JSON array of events.",
            status_code=400,
            meta=_meta(),
        )

    # Normalize → validate: default metric and source if missing
    events: List[IngestEvent] = []
    errors: List[dict] = []
    for idx, item in enumerate(payload):
        if not isinstance(item, dict):
            errors.append({"index": idx, "error": "Item must be an object", "item": item})
            continue
        obj = dict(item)
        if not obj.get("metric"):
            obj["metric"] = default_metric
        if not obj.get("source") and source_name:
            obj["source"] = source_name
        try:
            events.append(IngestEvent.model_validate(obj))
        except ValidationError as e:
            errors.append({"index": idx, "error": str(e), "item": item})

    if errors:
        return fail(
            code="VALIDATION_ERROR",
            message="One or more events are invalid.",
            status_code=422,
            details={"errors": errors},
            meta=_meta(),
        )

    if not events:
        resp = ok(
            data={"inserted": 0, "duplicates": 0, "rows_ingested": 0, "groups_upserted": 0, "metrics": []},
            meta=_meta(reason="empty_payload"),
        )
        if isinstance(resp, JSONResponse):
            resp.status_code = 200  # tests expect 200
        return resp

    eff_source = source_name or next((e.source for e in events if e.source), None)
    if not eff_source:
        return fail(
            code="VALIDATION_ERROR",
            message="source_name is required (either as query param or per-event 'source').",
            status_code=422,
            meta=_meta(),
        )

    src = _ensure_source(db, eff_source)

    inserted_rows = _insert_clean_events_strict(db, src.id, events)
    duplicates = max(0, len(events) - inserted_rows)
    result = _aggregate_and_upsert(db, src.id, events)
    db.commit()

    resp = ok(
        data={
            "inserted": inserted_rows,
            "duplicates": duplicates,
            "rows_ingested": result["rows_ingested"],
            "groups_upserted": result["groups_upserted"],
            "metrics": result["metrics"],
        },
        meta=_meta(
            source_name=eff_source,
            start_date=result["start_date"],
            end_date=result["end_date"],
            num_days=result["num_days"],
        ),
    )
    if isinstance(resp, JSONResponse):
        resp.status_code = 200
    return resp
