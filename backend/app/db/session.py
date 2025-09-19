# app/db/session.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from typing import Generator
from app.config import get_settings

settings = get_settings()

env_name = (settings.ENV or "dev").lower()
db_url = None

# Prefer explicit TEST_DATABASE_URL during pytest
if env_name == "test" or os.getenv("PYTEST_CURRENT_TEST"):
    db_url = settings.TEST_DATABASE_URL or os.getenv("TEST_DATABASE_URL")

if not db_url:
    db_url = settings.DATABASE_URL or os.getenv("DATABASE_URL")

if not db_url:
    # last-resort dev default (keep this consistent with your local dev!)
    db_url = "postgresql+psycopg2://postgres:postgres@localhost:5432/smartdata"

# Build engine with proper settings
if db_url.startswith("sqlite"):
    # SQLite: handle file and in-memory
    if db_url.endswith(":memory:") or db_url.endswith(":memory:?cache=shared"):
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,   
            future=True,
        )
    else:
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            future=True,
        )
else:
    engine = create_engine(db_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

print(f"[DB] Using {engine.url}")

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
