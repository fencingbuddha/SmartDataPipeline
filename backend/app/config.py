from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Extra

class Settings(BaseSettings):
    # environment: "dev" for running the app locally, "test" for pytest
    ENV: str = "dev"

    # DB URLs from .env (defaults None so we can detect when missing)
    DATABASE_URL: str | None = None
    TEST_DATABASE_URL: str | None = None

    # --- Auth / JWT ---
    JWT_SECRET: str = "dev"
    JWT_ALG: str = "HS256"
    JWT_ACCESS_MIN: int = 30
    JWT_REFRESH_DAYS: int = 7

    class Config:
        # .env should live in backend/.env (your current setup)
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = Extra.ignore  # <- don't crash on unrelated env keys

@lru_cache
def get_settings() -> Settings:
    return Settings()