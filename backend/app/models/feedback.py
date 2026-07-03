"""Feedback: a rating on an answer, accumulated as improvement candidates.

Tenant-scoped directly (``tenant_id``) so improvement logs can be filtered per
customer (permission-design.md §7-2). ``reason_category`` values come from
tenant_config.feedback.reason_categories, so it is a free string rather than a
DB enum.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models._common import TimestampMixin

if TYPE_CHECKING:
    from app.models.answer import Answer
    from app.models.tenant import Tenant

# Reference values only; not enforced as a DB enum.
RATING_GOOD = "good"
RATING_BAD = "bad"


class Feedback(TimestampMixin, Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    answer_id: Mapped[int] = mapped_column(
        ForeignKey("answer.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rating: Mapped[str] = mapped_column(nullable=False)
    # Only set for negative ratings; values from tenant_config.feedback.
    reason_category: Mapped[str | None] = mapped_column(nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped[Tenant] = relationship(back_populates="feedback")
    answer: Mapped[Answer] = relationship(back_populates="feedback")
