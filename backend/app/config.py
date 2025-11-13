# backend/app/config.py
from functools import lru_cache
from typing import List
import secrets

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # environment: "dev" for running the app locally, "test" for pytest
    ENV: str = "dev"

    DATABASE_URL: str | None = None
    TEST_DATABASE_URL: str | None = None

    # --- Auth / JWT ---
    JWT_SECRET: str | None = Field(None, description="JWT signing secret. Must be set outside dev/test.")
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

    # --- Scheduler (FR-9) ---
    # Toggle the background scheduler that runs KPI calculations and housekeeping.
    SCHEDULER_ENABLED: bool = True
    # IANA timezone name used by APScheduler (e.g., "UTC", "America/New_York").
    SCHEDULER_TZ: str = "UTC"
    # Optional dedicated job store URL. If None, use DATABASE_URL in your scheduler setup.
    SCHEDULER_DB_URL: str | None = None
    # Log level used by scheduled jobs; jobs should honor this when configuring loggers.
    SCHEDULER_LOG_LEVEL: str = "INFO"

    @model_validator(mode="after")
    def _check_jwt_secret(self):
        # In dev/test, auto-generate an ephemeral secret if none provided to avoid committing secrets.
        if self.ENV in ("dev", "test"):
            if not self.JWT_SECRET:
                self.JWT_SECRET = secrets.token_urlsafe(32)
            return self
        # In non-dev/test environments, require an explicit secret from env.
        if not self.JWT_SECRET:
            raise ValueError("JWT_SECRET must be set via environment for non-dev/test environments.")
        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
