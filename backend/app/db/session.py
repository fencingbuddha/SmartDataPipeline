import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.config import get_settings

settings = get_settings()

# Choose DB URL:
# - If ENV=test (or we're under pytest), use TEST_DATABASE_URL
# - Otherwise use DATABASE_URL
env_name = (settings.ENV or "dev").lower()

db_url = None
if env_name == "test" or os.getenv("PYTEST_CURRENT_TEST"):
    db_url = settings.TEST_DATABASE_URL or os.getenv("TEST_DATABASE_URL")

if not db_url:
    db_url = settings.DATABASE_URL or os.getenv("DATABASE_URL")

# Final safe default (local dev) if nothing was configured:
if not db_url:
    db_url = "postgresql+psycopg2://postgres:postgres@localhost:5432/smartdata"

engine = create_engine(db_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

# Helpful: prints exactly which DB URL is in use at startup
print(f"[DB] Using {engine.url}")

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
