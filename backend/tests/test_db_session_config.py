from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.config import Settings
import app.db.session as db_session


def test_select_database_url_prefers_test_setting(monkeypatch):
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "")
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(
        db_session,
        "settings",
        Settings(ENV="test", TEST_DATABASE_URL="sqlite:///tmp-test.db", DATABASE_URL=None),
        raising=False,
    )
    assert db_session._select_database_url() == "sqlite:///tmp-test.db"


def test_select_database_url_env_fallback(monkeypatch):
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///runtime.db")
    monkeypatch.setattr(
        db_session,
        "settings",
        Settings(ENV="prod", TEST_DATABASE_URL=None, DATABASE_URL=None),
        raising=False,
    )
    assert db_session._select_database_url() == "sqlite:///runtime.db"


def test_select_database_url_defaults(monkeypatch):
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setattr(
        db_session,
        "settings",
        Settings(ENV="prod", TEST_DATABASE_URL=None, DATABASE_URL=None),
        raising=False,
    )
    default = db_session._select_database_url()
    assert default.endswith("smartdata")


def test_build_engine_variants(tmp_path):
    memory_engine = db_session._build_engine("sqlite:///:memory:")
    try:
        assert "sqlite" in str(memory_engine.url)
        with memory_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    finally:
        memory_engine.dispose()

    file_url = f"sqlite:///{tmp_path/'db.sqlite'}"
    file_engine = db_session._build_engine(file_url)
    try:
        with file_engine.begin() as conn:
            conn.execute(text("SELECT 1"))
    finally:
        file_engine.dispose()


def test_get_db_closes_sessions(monkeypatch):
    created = []

    class DummySession:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    def factory():
        sess = DummySession()
        created.append(sess)
        return sess

    monkeypatch.setattr(db_session, "SessionLocal", factory, raising=False)

    gen = db_session.get_db()
    session = next(gen)
    assert session is created[0]
    with pytest.raises(StopIteration):
        next(gen)
    assert created[0].closed


def test_init_db_uses_current_engine(monkeypatch):
    engine = db_session._build_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr(db_session, "ENGINE", engine, raising=False)
    monkeypatch.setattr(db_session, "engine", engine, raising=False)
    monkeypatch.setattr(db_session, "SessionLocal", SessionLocal, raising=False)
    db_session.init_db()
    with engine.connect() as conn:
        tables = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='sources'")
        ).fetchall()
        assert tables
    engine.dispose()
