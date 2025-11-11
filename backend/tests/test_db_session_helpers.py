from __future__ import annotations

import importlib
from sqlalchemy import text

import app.db.session as session


class DummySettings:
    def __init__(self, env="dev", runtime=None, test=None):
        self.ENV = env
        self.DATABASE_URL = runtime
        self.TEST_DATABASE_URL = test


def test_select_database_prefers_test_url(monkeypatch):
    original = session.settings
    try:
        session.settings = DummySettings(env="test", runtime="runtime-db", test="sqlite:///memory")
        url = session._select_database_url()
        assert url == "sqlite:///memory"
    finally:
        session.settings = original


def test_select_database_falls_back_to_runtime(monkeypatch):
    original = session.settings
    try:
        session.settings = DummySettings(env="dev", runtime="postgresql://example", test=None)
        url = session._select_database_url()
        assert url == "postgresql://example"
    finally:
        session.settings = original


def test_build_engine_sqlite_memory():
    engine = session._build_engine("sqlite:///:memory:")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar_one()
            assert result == 1
    finally:
        engine.dispose()
