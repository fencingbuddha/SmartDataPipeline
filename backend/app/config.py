from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5433/sdp_dev"
    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()
