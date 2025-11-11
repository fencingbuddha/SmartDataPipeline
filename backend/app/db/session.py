from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

settings = get_settings()

def _select_database_url() -> str:
    env_name = (settings.ENV or "dev").lower()

    if env_name == "test" or os.getenv("PYTEST_CURRENT_TEST"):
        test_url = settings.TEST_DATABASE_URL or os.getenv("TEST_DATABASE_URL")
        if test_url:
            return test_url

    runtime_url = settings.DATABASE_URL or os.getenv("DATABASE_URL")
    if runtime_url:
        return runtime_url

    return "postgresql+psycopg2://postgres:postgres@localhost:5433/smartdata"


def _enforce_ssl_requirements(raw_url: str) -> str:
    url_obj = make_url(raw_url)
    backend = url_obj.get_backend_name()

    if settings.DB_REQUIRE_SSL and backend.startswith("postgresql"):
        if "sslmode" not in url_obj.query:
            new_query = dict(url_obj.query)
            new_query["sslmode"] = "require"
            url_obj = url_obj.set(query=new_query)

    expected_role = settings.DB_APP_ROLE
    if expected_role and url_obj.username and url_obj.username != expected_role:
        raise RuntimeError(
            f"DATABASE_URL user '{url_obj.username}' does not match required role '{expected_role}'"
        )

    return str(url_obj)


def _build_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if url.endswith(":memory:") or url.endswith(":memory:?cache=shared"):
            return create_engine(
                url,
                connect_args=connect_args,
                poolclass=StaticPool,
                future=True,
            )
        return create_engine(url, connect_args=connect_args, future=True)

    return create_engine(url, pool_pre_ping=True, future=True)


DATABASE_URL = _enforce_ssl_requirements(_select_database_url())
ENGINE: Engine = _build_engine(DATABASE_URL)
engine: Engine = ENGINE  # alias used in tests and legacy imports
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=ENGINE,
    autocommit=False,
    autoflush=False,
    future=True,
)

print(f"[DB] Using {ENGINE.url}")

# Ensure SQLite databases have their tables created eagerly.
# For Postgres we rely on migrations/startup hooks.
if ENGINE.dialect.name == "sqlite":
    from app.db.base import Base  # pylint: disable=import-outside-toplevel

    Base.metadata.create_all(bind=ENGINE)


def get_engine() -> Engine:
    return ENGINE


def get_sessionmaker() -> sessionmaker[Session]:
    return SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Lazy import to avoid circular dependency at module import time
    from app.db.base import Base  # pylint: disable=import-outside-toplevel

    Base.metadata.create_all(bind=ENGINE)
