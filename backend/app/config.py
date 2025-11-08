# backend/app/config.py
from functools import lru_cache
from typing import List

from pydantic import Field
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

    # --- Security controls ---
    FORCE_HTTPS: bool = False
    TRUSTED_HOSTS: List[str] = Field(
        default_factory=lambda: [
            "localhost",
            "127.0.0.1",
            "testserver",
            "test",
        ]
    )
    HSTS_MAX_AGE: int = 31536000  # 1 year
    CONTENT_SECURITY_POLICY: str = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; "
        "font-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    DB_APP_ROLE: str | None = None
    DB_REQUIRE_SSL: bool = True
    APP_ENCRYPTION_KEY: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> Settings:
    return Settings()
