import os
import importlib
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5433/smartdata_test",
)

for mod in (
    "app.models.source",
    "app.models.clean_event",
    "app.models.metric_daily",
    "app.models.raw_upload",
    "app.models.raw_event",
):
    try:
        importlib.import_module(mod)
    except Exception:
        pass

from app.db.base import Base


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL, future=True)
    # start from a clean slate
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def db(engine):
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def reset_db(engine):
    """
    Per-test clean DB. Drop & recreate all tables so constraints and sequences reset.
    (Slower but simplest & most reliable for now.)
    """
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield

@pytest.fixture(autouse=True)
def _auto_reset(reset_db):
    """Drop & recreate all tables before every test for full isolation."""
    pass