"""Logging configuration.

Applies LOG_LEVEL from settings. Secrets must never be logged; this only sets
up formatting/level and does not emit any configuration values.
"""

import logging

from app.core.config import get_settings


def setup_logging() -> None:
    """Configure root logging based on the configured LOG_LEVEL."""
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
