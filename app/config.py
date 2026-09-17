from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed access to environment variables. Never put secrets in code."""

    app_env: str = "dev"
    secret_key: str = "change-me-to-a-long-random-string"
    access_token_expire_minutes: int = 60 * 24

    database_url: str = "sqlite:///./spendsense.db"

    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"

    cache_ttl_seconds: int = 60

    enable_scheduler: bool = True
    auto_categorize_interval_minutes: int = 5
    report_cron_hour: int = 8
    report_cron_minute: int = 0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()