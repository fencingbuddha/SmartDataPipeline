from typing import Tuple, Optional
import io
import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.models import Source, RawEvent, CleanEvent
from datetime import datetime, timezone
import numpy as np

def _native(v):
    # Normalize Pandas/NumPy/datetime to JSON-safe Python types
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
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
    db.flush()
    return src

def _read_to_df(file_bytes: bytes, content_type: str) -> pd.DataFrame:
    try:
        if content_type and "json" in content_type:
            return pd.read_json(io.BytesIO(file_bytes))
        return pd.read_csv(io.BytesIO(file_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unable to parse file: {e}")

def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    # find columns (common variants allowed)
    ts = next((c for c in df.columns if c.lower() in {"timestamp","time","date","datetime"}), None)
    if not ts:
        raise HTTPException(status_code=400, detail="Missing timestamp/time/date column.")
    val = next((c for c in df.columns if c.lower() in {"value","amount","count","qty","quantity"}), None)
    if not val:
        raise HTTPException(status_code=400, detail="Missing numeric value column.")
    metric = next((c for c in df.columns if c.lower() in {"metric","name","metric_name"}), None)

    norm = pd.DataFrame({
        "timestamp": pd.to_datetime(df[ts], errors="coerce"),
        "metric": df[metric].astype(str) if metric else "value",
        "value": pd.to_numeric(df[val], errors="coerce")
    })
    norm = norm.dropna(subset=["timestamp","value"])
    if norm.empty:
        raise HTTPException(status_code=400, detail="No valid rows after cleaning.")
    return norm

def ingest_file(db: Session, source_name: str, file_bytes: bytes, content_type: str, filename: Optional[str] = None) -> Tuple[int,int]:
    src = _get_or_create_source(db, source_name)
    df_raw = _read_to_df(file_bytes, content_type or "text/csv")
    norm = _normalize(df_raw)

    # stage: raw_events
    raw_count = 0
    for _, r in df_raw.iterrows():
        raw_payload = {k: _native(v) for k, v in r.to_dict().items()}
        db.add(RawEvent(
            source_id=src.id,
            filename=filename,
            content_type=content_type,
            payload=raw_payload,
            received_at=datetime.utcnow(),
        ))
        raw_count += 1

    # build rows for bulk upsert into clean_events (idempotent)
    rows_clean = []
    for _, r in norm.iterrows():
        ts_val = r["timestamp"]
        if isinstance(ts_val, pd.Timestamp):
            # ensure tz-aware UTC
            if ts_val.tzinfo is None:
                ts_val = ts_val.tz_localize("UTC")
            ts_py = ts_val.to_pydatetime()
        else:
            # python datetime
            ts_py = ts_val
            if ts_py.tzinfo is None:
                ts_py = ts_py.replace(tzinfo=timezone.utc)

        rows_clean.append({
            "source_id": src.id,
            "ts": ts_py,
            "metric": str(r["metric"]),
            "value": float(r["value"]),
        })

    clean_count = 0
    if rows_clean:
        stmt = insert(CleanEvent).values(rows_clean).on_conflict_do_nothing(
            index_elements=["source_id", "ts", "metric"]
        )
        result = db.execute(stmt)
        clean_count = result.rowcount or 0

    db.commit()
    return raw_count, clean_count
