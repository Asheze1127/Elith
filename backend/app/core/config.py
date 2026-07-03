"""Application (environment) config loaded from .env via pydantic-settings.

This holds app-wide startup conditions (DB URL, provider selection, log level),
which are distinct from tenant_config (per-tenant behavior stored in the DB).
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Module-relative .env path so loading does not depend on the process CWD.
# parents[2] resolves from app/core/config.py -> backend/, i.e. backend/.env.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """App-wide environment settings.

    Defaults keep the app importable/bootable without a live DB or secrets.
    """

    # local -> Gemini free API / no key -> mock (provider selection handled in #4)
    ENVIRONMENT: str = "local"
    # SQLAlchemy URL using the postgresql+psycopg dialect (matches docker-compose db)
    DATABASE_URL: str = "postgresql+psycopg://elith:elith@db:5432/elith"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (single read of the environment)."""
    return Settings()
