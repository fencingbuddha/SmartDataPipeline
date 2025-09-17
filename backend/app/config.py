from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # environment: "dev" for running the app locally, "test" for pytest
    ENV: str = "dev"

    # URLs come from .env; defaults are None so we can detect if you forgot them
    DATABASE_URL: str | None = None
    TEST_DATABASE_URL: str | None = None

    class Config:
        # .env should live in the same working directory you launch uvicorn from (usually backend/.env)
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> Settings:
    return Settings()
