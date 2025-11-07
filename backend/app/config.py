# backend/app/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # environment: "dev" for running the app locally, "test" for pytest
    ENV: str = "dev"

    # URLs come from .env; defaults are None so we can detect if you forgot them
    DATABASE_URL: str | None = None
    TEST_DATABASE_URL: str | None = None

    # --- Auth / JWT ---
    JWT_SECRET: str  # <-- required, no default
    JWT_ALG: str = "HS256"
    JWT_ACCESS_MIN: int = 30
    JWT_REFRESH_DAYS: int = 7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> Settings:
    return Settings()