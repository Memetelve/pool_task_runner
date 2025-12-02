"""Application configuration via environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the JobRunner service."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "JobRunner"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./jobrunner.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    default_queue: str = "default"
    default_working_dir: str = "."
    allowed_workdirs: list[str] = Field(default_factory=list)
    command_timeout_seconds: int = 3600
    default_max_jobs_per_user: int = 100

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
