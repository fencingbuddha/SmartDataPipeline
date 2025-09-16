import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import engine, SessionLocal
from app.db.base import Base
import app.models


# ---------- Create schema once per test session ----------
@pytest.fixture(scope="session", autouse=True)
def _create_schema_once():
    Base.metadata.create_all(bind=engine)


# ---------- Clean tables before each test (dialect-aware, dynamic) ----------
@pytest.fixture(autouse=True)
def clean_db():
    dialect = engine.dialect.name  # 'postgresql' or 'sqlite'
    # Build table list dynamically from metadata
    table_names = [t.name for t in Base.metadata.sorted_tables]
    if not table_names:
        yield
        return

    with engine.begin() as conn:
        if dialect == "postgresql":
            # TRUNCATE all known tables in one shot, reset identities, cascade FKs
            tables_csv = ", ".join(table_names)
            conn.execute(
                text(f"TRUNCATE TABLE {tables_csv} RESTART IDENTITY CASCADE")
            )
        else:
            # SQLite (no TRUNCATE): delete from each table
            # Delete in reverse dependency order to avoid FK issues
            for t in reversed(Base.metadata.sorted_tables):
                conn.execute(text(f"DELETE FROM {t.name}"))
    yield


# ---------- FastAPI DB dependency override (optional but recommended) ----------
def _override_get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _try_set_dependency_override():
    try:
        from app.deps import get_db as _get_db  # type: ignore
        app.dependency_overrides[_get_db] = _override_get_db
        return
    except Exception:
        pass

    try:
        from app.db.session import get_db as _get_db  # type: ignore
        app.dependency_overrides[_get_db] = _override_get_db
        return
    except Exception:
        pass

@pytest.fixture()
def reset_db(clean_db):
    yield 

@pytest.fixture()
def client():
    _try_set_dependency_override()
    c = TestClient(app)
    try:
        yield c
    finally:
        # prevent bleed-over across tests
        app.dependency_overrides = {}
