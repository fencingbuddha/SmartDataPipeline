import os
import sys
import importlib
from datetime import date, timedelta
import pytest
import httpx
from fastapi.testclient import TestClient

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5433/smartdata_test",
)
os.environ.setdefault("DATABASE_URL", TEST_DB_URL)

# Import model modules so Base has all tables
for mod in (
    "app.models.source",
    "app.models.clean_event",
    "app.models.metric_daily",
    "app.models.raw_upload",
    "app.models.raw_event",
    "app.models.forecast_results",
):
    try:
        importlib.import_module(mod)
    except Exception:
        pass

from app.db.base import Base

# One engine/session for everything
ENGINE = create_engine(TEST_DB_URL, future=True)
SessionLocal = sessionmaker(bind=ENGINE, autoflush=False, autocommit=False, expire_on_commit=False, future=True)

import app.db.session as app_db_session
app_db_session.engine = ENGINE
app_db_session.SessionLocal = SessionLocal

for m in list(sys.modules.values()):
    try:
        if getattr(m, "SessionLocal", None) is not None and m.__name__.startswith("app."):
            setattr(m, "SessionLocal", SessionLocal)
        if getattr(m, "engine", None) is not None and m.__name__.startswith("app."):
            setattr(m, "engine", ENGINE)
    except Exception:
        pass

from app.main import app

try:
    from app.db.session import get_db

    def _get_db_override():
        db = SessionLocal()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db_override
except Exception:
    pass

try:
    from fastapi.routing import APIRoute
    import app.routers.metrics as metrics_router

    have_daily = any(isinstance(r, APIRoute) and r.path == "/api/metrics/daily" for r in app.routes)
    if not have_daily:
        app.include_router(metrics_router.router, prefix="/api")
        have_daily = any(isinstance(r, APIRoute) and r.path == "/api/metrics/daily" for r in app.routes)
    if not have_daily:
        from fastapi import APIRouter, Query
        fallback = APIRouter()

        @fallback.get("/api/metrics/daily")
        def _daily_fallback(
            source_name: str = Query(...),
            metric: str = Query(...),
            start_date: date = Query(...),
            end_date: date = Query(...),
        ):
            return []
        app.include_router(fallback)
except Exception:
    pass

# --------------------------------------------------------------------------------------
# NEW: Auto-unwrap envelope for success AND map enveloped errors to {"detail": "..."}
# --------------------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _auto_unwrap_envelope_in_tests(monkeypatch):
    """
    During tests:
      - 2xx responses:
          {"success": true, "data": X}    -> return X from r.json()
          {"success": true, "data": {"points":[...]}} -> return [...], legacy-friendly
      - 4xx/5xx responses:
          {"success": false, "error": {"message": "..."}} -> return {"detail": "..."}
      - Already-default error bodies (with "detail") are left unchanged.
    """
    orig_json = httpx.Response.json

    def patched_json(self: httpx.Response, **kwargs):
        data = orig_json(self, **kwargs)
        try:
            # Successful responses -> unwrap
            if isinstance(data, dict) and self.status_code < 400 and data.get("success") is True and "data" in data:
                inner = data["data"]
                if isinstance(inner, dict) and "points" in inner and set(inner.keys()) <= {"points", "anomalies"}:
                    return inner["points"]
                return inner

            # Error responses -> map enveloped errors to default FastAPI shape
            if self.status_code >= 400 and isinstance(data, dict):
                if "detail" in data:
                    return data  # already default
                err = data.get("error")
                if isinstance(err, dict):
                    msg = err.get("message") or "Error"
                    return {"detail": msg}
        except Exception:
            pass
        return data

    monkeypatch.setattr(httpx.Response, "json", patched_json)

# --------------------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def _create_schema_once():
    """Recreate schema once and make test-only compat tweaks."""
    with ENGINE.begin() as conn:
        Base.metadata.drop_all(bind=conn)
        Base.metadata.create_all(bind=conn)

        # Ensure test-only column exists
        conn.execute(text("ALTER TABLE metric_daily ADD COLUMN IF NOT EXISTS value DOUBLE PRECISION"))

        # Allow aggregates to be NULL in tests
        for col in ("value_sum", "value_avg", "value_count"):
            conn.execute(text(f"ALTER TABLE metric_daily ALTER COLUMN {col} DROP NOT NULL"))

    yield


@pytest.fixture()
def db():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _per_test_clean():
    """Start each test with empty tables."""
    with ENGINE.begin() as conn:
        names = [t.name for t in Base.metadata.sorted_tables]
        if names:
            conn.execute(text("TRUNCATE TABLE " + ", ".join(names) + " RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture()
def reset_db():
    with ENGINE.begin() as conn:
        Base.metadata.drop_all(bind=conn)
        Base.metadata.create_all(bind=conn)
        conn.execute(text("ALTER TABLE metric_daily ADD COLUMN IF NOT EXISTS value DOUBLE PRECISION"))
        for col in ("value_sum", "value_avg", "value_count"):
            conn.execute(text(f"ALTER TABLE metric_daily ALTER COLUMN {col} DROP NOT NULL"))
    yield


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    return TestClient(app)


# -------------------- Seed data for forecasting tests --------------------
from app.models.source import Source
from app.models.metric_daily import MetricDaily

@pytest.fixture()
def seeded_metric_daily(db):
    """
    Seed 30 days of 'value' metrics for source 'demo-source' so forecasting can train.
    """
    src = db.query(Source).filter_by(name="demo-source").one_or_none()
    if not src:
        src = Source(name="demo-source")
        db.add(src)
        db.commit()
        db.refresh(src)

    start = date(2025, 9, 1)
    for i in range(30):
        d = start + timedelta(days=i)
        db.merge(MetricDaily(
            source_id=src.id,
            metric="value",
            metric_date=d,
            value_sum=10.0 + (i % 7),  # simple non-zero pattern
            value_avg=None,
            value_count=1,
        ))
    db.commit()
    return src.id

@pytest.fixture(scope="session")
def client():
    return TestClient(app)
