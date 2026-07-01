"""Application (environment) config loaded from .env via pydantic-settings.

This holds app-wide startup conditions (DB URL, provider selection, log level),
which are distinct from tenant_config (per-tenant behavior stored in the DB).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App-wide environment settings.

    Defaults keep the app importable/bootable without a live DB or secrets.
    """

    # local -> Gemini free API / no key -> mock (provider selection handled by providers.factory)
    ENVIRONMENT: str = "local"
    # SQLAlchemy URL using the postgresql+psycopg dialect (matches docker-compose db)
    DATABASE_URL: str = "postgresql+psycopg://elith:elith@db:5432/elith"
    # Gemini free-tier API key. Empty default keeps the app bootable without secrets;
    # when empty the provider factory falls back to the deterministic mock.
    GEMINI_API_KEY: str = ""
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (single read of the environment)."""
    return Settings()
