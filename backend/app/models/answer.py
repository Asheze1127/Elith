"""Answer: a generated response to a query, scoped to a tenant.

``status`` and ``mode`` are stored as plain strings (not DB enums) because the
allowed values are driven by tenant_config (answer.modes,
low_confidence_action) and must not require a schema migration when a tenant
adds a mode. See permission-design.md §5 and the evaluation log in §7-1.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models._common import TimestampMixin

if TYPE_CHECKING:
    from app.models.citation import Citation
    from app.models.feedback import Feedback
    from app.models.tenant import Tenant

# Reference values only; the effective set comes from tenant_config, so these
# are not enforced as a DB enum (see module docstring).
STATUS_ANSWERED = "answered"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_NO_DATA = "no_data"


class Answer(TimestampMixin, Base):
    __tablename__ = "answer"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    # Answer mode (e.g. external / internal); values defined by tenant_config.
    mode: Mapped[str | None] = mapped_column(nullable=True)

    tenant: Mapped[Tenant] = relationship(back_populates="answers")
    citations: Mapped[list[Citation]] = relationship(
        back_populates="answer",
        cascade="all, delete-orphan",
    )
    feedback: Mapped[list[Feedback]] = relationship(
        back_populates="answer",
        cascade="all, delete-orphan",
    )
