"""Workspace: a region inside a tenant (department / site / line).

Used to narrow retrieval scope (permission-design.md §3, ``workspace_id``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models._common import TimestampMixin

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.tenant import Tenant


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspace"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(nullable=False)

    tenant: Mapped[Tenant] = relationship(back_populates="workspaces")
    documents: Mapped[list[Document]] = relationship(back_populates="workspace")
