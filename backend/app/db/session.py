from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
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


DATABASE_URL = _select_database_url()
ENGINE: Engine = _build_engine(DATABASE_URL)
engine: Engine = ENGINE  # alias used in tests and legacy imports
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=ENGINE,
    autocommit=False,
    autoflush=False,
    future=True,
)

print(f"[DB] Using {ENGINE.url}")


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
