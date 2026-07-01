"""Shared column helpers for ORM models.

Centralized so every table uses the same primary-key and timestamp conventions
instead of repeating the definitions in each model.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Adds server-managed created_at / updated_at columns.

    ``server_default``/``onupdate`` keep timestamps correct even for writes that
    bypass the ORM (e.g. raw SQL in migrations or ingestion jobs).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
