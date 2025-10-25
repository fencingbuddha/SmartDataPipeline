import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure the application runs in test/sqlite mode *before* importing any app modules
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("DATABASE_URL", "sqlite://")

# Import the DB session module first so we can patch it before the app is imported
import app.db.session as app_db_session  # type: ignore

# --- Use a single in-memory SQLite DB for the whole test session ---
ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True,
)
SessionTesting = sessionmaker(bind=ENGINE, autocommit=False, autoflush=False, future=True)

# --- Ensure tests and app code share the SAME in-memory engine/sessionmaker ---
# Make sure any references inside app.db.session use this shared in-memory engine/sessionmaker
setattr(app_db_session, "ENGINE", ENGINE)
setattr(app_db_session, "engine", ENGINE)  # in case code uses lowercase name
app_db_session.SessionLocal = SessionTesting
app_db_session.get_engine = lambda: ENGINE            # type: ignore
app_db_session.get_sessionmaker = lambda: SessionTesting  # type: ignore

# Also patch the package-level app.db for tests that import SessionLocal from app.db
import app.db as app_db_pkg  # type: ignore
setattr(app_db_pkg, "ENGINE", ENGINE)
setattr(app_db_pkg, "engine", ENGINE)
app_db_pkg.SessionLocal = SessionTesting

from app.db.session import get_db
from app.main import app

def _create_sqlite_test_schema(conn):
    """Create the minimal tables our tests expect, using SQLite-compatible DDL."""
    conn.execute(text("PRAGMA foreign_keys=ON"))
    # sources table
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL UNIQUE
        )
    """))
    # raw_events table used by ingest pipeline to log receipts
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS raw_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            received_at DATETIME NOT NULL,
            filename VARCHAR NOT NULL,
            content_type VARCHAR NOT NULL,
            payload TEXT NOT NULL,
            FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
        )
    """))
    # Helpful index for lookups by source/time
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_raw_events_source_received
        ON raw_events (source_id, received_at)
    """))
    # clean_events table (subset of columns used in tests)
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS clean_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            ts DATETIME NOT NULL,
            metric VARCHAR NOT NULL,
            value NUMERIC NOT NULL,
            flags TEXT DEFAULT '{}' NOT NULL,
            FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
        )
    """))
    # Helpful indexes for queries used in tests
    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_clean_events_source_ts_metric ON clean_events (source_id, ts, metric)"))
    # metric_daily table for aggregated KPI values used by tests
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS metric_daily (
            metric_date DATE NOT NULL,
            source_id INTEGER NOT NULL,
            metric VARCHAR(64) NOT NULL,
            -- single-value column used by some tests when seeding data
            value NUMERIC,
            -- aggregate columns used by the app/API
            value_sum NUMERIC DEFAULT 0 NOT NULL,
            value_avg NUMERIC DEFAULT 0 NOT NULL,
            value_count INTEGER DEFAULT 0 NOT NULL,
            value_distinct INTEGER,
            PRIMARY KEY (metric_date, source_id, metric),
            FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
        )
    """))
    # Helpful index for date filtering
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_metric_daily_date ON metric_daily (metric_date)"))

    # forecast_results table for model outputs
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS forecast_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            metric VARCHAR NOT NULL,
            target_date DATE NOT NULL,
            yhat NUMERIC NOT NULL,
            yhat_lower NUMERIC,
            yhat_upper NUMERIC,
            model_version VARCHAR,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
        )
    """))
    # Ensure idempotent upsert behavior in SQLite (matches ON CONFLICT target)
    conn.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_forecast_results_src_metric_date
        ON forecast_results (source_id, metric, target_date)
    """))
    # Optional helper index for date-range queries
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_forecast_results_date
        ON forecast_results (target_date)
    """))

    # forecast_models table (used by /api/forecast/health)
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS forecast_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER NOT NULL,
            metric VARCHAR NOT NULL,
            model_name VARCHAR NOT NULL,
            model_params TEXT,
            window_n INTEGER NOT NULL,
            horizon_n INTEGER NOT NULL,
            trained_at DATETIME,
            train_start DATE,
            train_end DATE,
            mape NUMERIC,
            notes TEXT,
            FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
        )
    """))
    conn.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_forecast_models_src_metric_window
        ON forecast_models (source_id, metric, window_n)
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_forecast_models_metric_window
        ON forecast_models (metric, window_n)
    """))


@pytest.fixture(scope="session")
def _db_engine():
    # Yield the shared engine in case tests need it
    with ENGINE.begin() as conn:
        _create_sqlite_test_schema(conn)
    yield ENGINE


@pytest.fixture(scope="session")
def _session_factory(_db_engine):
    yield SessionTesting


@pytest.fixture(scope="function")
def db(_session_factory, reset_db):
    session = _session_factory()

    # Override FastAPI dependency to use the testing session
    def _override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield session
    finally:
        # Rollback anything left open and close session
        session.rollback()
        session.close()
        # Remove override so other tests can reapply
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="function")
def db_session(db):
    """
    Some tests expect a `db_session` fixture. Reuse the per-test `db` session.
    """
    yield db


@pytest.fixture(scope="function")
def session(db):
    """
    Some tests refer to a generic `session` fixture. Alias to `db` as well.
    """
    yield db


@pytest.fixture(scope="function")
def reset_db(_db_engine):
    """Drop all user tables in the in-memory SQLite database between tests.

    We intentionally avoid ORM metadata.create_all() because some models use
    PostgreSQL-specific types like JSONB. Our API routes create tables they need
    with portable SQL when required. This keeps SQLite happy and tests isolated.
    """
    # Before each test, purge all tables
    with _db_engine.begin() as conn:
        # Find all tables except SQLite internal ones
        tables = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )).scalars().all()
        for t in tables:
            conn.execute(text(f"DROP TABLE IF EXISTS {t}"))
        # Recreate the minimal schema required by tests
        _create_sqlite_test_schema(conn)
        # Ensure every route uses the shared in-memory ENGINE, even if a test
        # constructs its own TestClient(app) without our 'client' fixture.
        def _override_get_db_for_all_tests():
            session = SessionTesting()  # bound to the shared ENGINE (StaticPool)
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = _override_get_db_for_all_tests
    yield
    # After each test, ensure it's empty again (belt-and-suspenders)
    with _db_engine.begin() as conn:
        tables = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )).scalars().all()
        for t in tables:
            conn.execute(text(f"DROP TABLE IF EXISTS {t}"))
        _create_sqlite_test_schema(conn)


@pytest.fixture(scope="function")
def client(db):
    """A TestClient that talks to the FastAPI app with our DB override applied per-test.

    Depending on the `db` fixture ensures the FastAPI dependency override is active and the
    SQLite test schema exists for each test that uses this client.
    """
    with TestClient(app) as c:
        yield c


# --- New fixture: seeded_metric_daily ---
@pytest.fixture(scope="function")
def seeded_metric_daily(db):
    """
    Seed a flat daily series for the default metric ('events_total') for the last 120 days.
    Returns a dict with source info that tests can use.
    """
    src_name = "seeded-source"
    metric = "events_total"

    # Ensure source exists and get its id
    existing_id = db.execute(text("SELECT id FROM sources WHERE name = :n"), {"n": src_name}).scalar()
    if existing_id is None:
        db.execute(text("INSERT INTO sources (name) VALUES (:n)"), {"n": src_name})
        db.commit()
        existing_id = db.execute(text("SELECT id FROM sources WHERE name = :n"), {"n": src_name}).scalar()
    source_id = int(existing_id)

    # Remove any prior seeded rows for idempotency
    db.execute(
        text("DELETE FROM metric_daily WHERE source_id = :sid AND metric = :m"),
        {"sid": source_id, "m": metric},
    )

    from datetime import date, timedelta

    today = date.today()
    start = today - timedelta(days=119)  # inclusive window: 120 days total
    daily_value = 10.0  # flat series

    rows = []
    d = start
    while d <= today:
        rows.append(
            {
                "metric_date": d.isoformat(),
                "source_id": source_id,
                "metric": metric,
                "value": daily_value,
                "value_sum": daily_value,
                "value_avg": daily_value,
                "value_count": 1,
                "value_distinct": None,
            }
        )
        d += timedelta(days=1)

    db.execute(
        text(
            """
            INSERT INTO metric_daily
                (metric_date, source_id, metric, value, value_sum, value_avg, value_count, value_distinct)
            VALUES
                (:metric_date, :source_id, :metric, :value, :value_sum, :value_avg, :value_count, :value_distinct)
            """
        ),
        rows,
    )
    db.commit()

    return {
        "source_name": src_name,
        "source_id": source_id,
        "metric": metric,
        "start_date": start,
        "end_date": today,
    }
