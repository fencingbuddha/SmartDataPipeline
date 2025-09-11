import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import engine, SessionLocal
from sqlalchemy import text

@pytest.fixture(scope="session", autouse=True)
def _create_schema_once():
    # Ensure all tables exist before running tests (safe if already created)
    from app.db.base import Base
    import app.models  # registers models
    Base.metadata.create_all(bind=engine)

@pytest.fixture(autouse=True)
def clean_db():
    # Truncate tables before each test for deterministic results
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE raw_events RESTART IDENTITY CASCADE"))
        conn.execute(text("TRUNCATE TABLE clean_events RESTART IDENTITY CASCADE"))
        conn.execute(text("TRUNCATE TABLE sources RESTART IDENTITY CASCADE"))
    yield

@pytest.fixture()
def client():
    return TestClient(app)
