"""Tenant: the top-level data and config boundary (a customer).

Every business row is reachable from a tenant via ``tenant_id`` so that all
queries can be scoped to a single customer (permission-design.md §3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models._common import TimestampMixin

if TYPE_CHECKING:
    from app.models.answer import Answer
    from app.models.chunk import Chunk
    from app.models.document import Document
    from app.models.feedback import Feedback
    from app.models.tenant_config import TenantConfig
    from app.models.workspace import Workspace


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenant"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(nullable=False)

    config: Mapped[TenantConfig | None] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
        uselist=False,
    )
    workspaces: Mapped[list[Workspace]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list[Document]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    answers: Mapped[list[Answer]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    feedback: Mapped[list[Feedback]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
