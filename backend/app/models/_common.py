"""Shared column helpers for ORM models.

Centralized so every table uses the same primary-key and timestamp conventions
instead of repeating the definitions in each model.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Adds created_at / updated_at columns.

    ``server_default`` makes the DB fill the initial value at INSERT time, so
    created_at is set even for rows inserted via raw SQL.

    ``onupdate`` is NOT a DB trigger: it is applied only when SQLAlchemy flushes
    an UPDATE. An UPDATE issued via raw SQL (migrations, manual queries, or other
    tools) will therefore NOT refresh updated_at automatically -- the caller must
    set it explicitly in that case.
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
