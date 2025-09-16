from typing import Tuple, Optional, List, Dict, Any
import io, json
import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.models import Source, RawEvent, CleanEvent
from datetime import datetime, timezone
import numpy as np

def _native(v):
    if isinstance(v, (pd.Timestamp, datetime)):
        # always UTC ISO
        if isinstance(v, pd.Timestamp):
            v = v.tz_convert("UTC") if v.tzinfo else v.tz_localize("UTC")
            return v.to_pydatetime().astimezone(timezone.utc).isoformat()
        return v.astimezone(timezone.utc).isoformat()
    if isinstance(v, (np.integer,)):  return int(v)
    if isinstance(v, (np.floating,)): return float(v)
    if pd.isna(v):                    return None
    return v

def _get_or_create_source(db: Session, source_name: str) -> Source:
    src = db.execute(select(Source).where(Source.name == source_name)).scalar_one_or_none()
    if src: return src
    src = Source(name=source_name)
    db.add(src); db.flush()
    return src

def _read_to_df(file_bytes: bytes, content_type: str) -> pd.DataFrame:
    try:
        if "json" in (content_type or ""):
            # handle array JSON or NDJSON
            txt = file_bytes.decode()
            try:
                data = json.loads(txt)
                if isinstance(data, dict): data = [data]
                return pd.DataFrame(data)
            except json.JSONDecodeError:
                lines = [json.loads(l) for l in txt.strip().splitlines() if l.strip()]
                return pd.DataFrame(lines)
        return pd.read_csv(io.BytesIO(file_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unable to parse file: {e}")

def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    # STRICT: raise on any bad row (no dropna)
    ts_col = next((c for c in df.columns if c.lower() in {"timestamp","time","date","datetime"}), None)
    if not ts_col:
        raise HTTPException(status_code=400, detail="Missing timestamp/time/date column.")
    val_col = next((c for c in df.columns if c.lower() in {"value","amount","count","qty","quantity"}), None)
    if not val_col:
        raise HTTPException(status_code=400, detail="Missing numeric value column.")
    metric_col = next((c for c in df.columns if c.lower() in {"metric","name","metric_name"}), None)

    ts = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
    val = pd.to_numeric(df[val_col], errors="coerce")
    if ts.isna().any():
        raise HTTPException(status_code=400, detail="Invalid timestamp value encountered.")
    if val.isna().any():
        raise HTTPException(status_code=400, detail="Invalid numeric value encountered.")

    metric = df[metric_col].astype(str) if metric_col else pd.Series(["value"] * len(df))
    return pd.DataFrame({"timestamp": ts, "metric": metric.values, "value": val.values})

def ingest_file(
    db: Session,
    source_name: str,
    file_bytes: bytes,
    content_type: str,
    filename: Optional[str] = None,
) -> Tuple[int, int, int]:
    """Return (raw_count, inserted, duplicates)."""
    # Parse and validate first (no DB work yet)
    df_raw = _read_to_df(file_bytes, content_type or "text/csv")
    norm = _normalize(df_raw)

    # Prepare rows for clean_events
    rows_clean: List[Dict[str, Any]] = []
    for _, r in norm.iterrows():
        ts_val = r["timestamp"]
        if isinstance(ts_val, pd.Timestamp):
            ts_py = ts_val.to_pydatetime()
        else:
            ts_py = ts_val
        if ts_py.tzinfo is None:
            ts_py = ts_py.replace(tzinfo=timezone.utc)
        rows_clean.append({
            "source_id": None,  # fill after we know source_id
            "ts": ts_py,
            "metric": str(r["metric"]),
            "value": float(r["value"]),
        })

    raw_count = 0
    inserted = 0
    duplicates = 0
    now_utc = datetime.now(timezone.utc)

    # >>> Begin the transaction BEFORE any writes <<< #
    with db.begin():
        src = _get_or_create_source(db, source_name)

        # stage raw_events
        for _, r in df_raw.iterrows():
            db.add(RawEvent(
                source_id=src.id,
                filename=filename,
                content_type=content_type,
                payload={k: _native(v) for k, v in r.to_dict().items()},
                received_at=now_utc,
            ))
            raw_count += 1

        # upsert clean_events
        if rows_clean:
            for rc in rows_clean:
                rc["source_id"] = src.id
            stmt = insert(CleanEvent).values(rows_clean).on_conflict_do_nothing(
                index_elements=["source_id", "ts", "metric"]
            )
            result = db.execute(stmt)
            inserted = int(result.rowcount or 0)
            duplicates = max(len(rows_clean) - inserted, 0)

    return raw_count, inserted, duplicates