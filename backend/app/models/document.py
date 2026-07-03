"""Document: a source material belonging to a tenant (and optionally a workspace).

Carries ``updated_at`` (via TimestampMixin) plus a domain ``source_updated_at``
so the pipeline can raise stale-source warnings (multi-tenant-design.md
``warnings.stale_sources``). workspace_id is nullable: tenant-wide documents may
not belong to a specific workspace.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models._common import TimestampMixin

if TYPE_CHECKING:
    from app.models.chunk import Chunk
    from app.models.tenant import Tenant
    from app.models.workspace import Workspace


class Document(TimestampMixin, Base):
    __tablename__ = "document"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Nullable: a document may be tenant-wide rather than scoped to one workspace.
    #
    # Same-tenant invariant: when set, the referenced workspace MUST belong to the
    # same tenant, i.e. document.tenant_id == workspace.tenant_id. A single-column
    # FK cannot enforce this at the DB level (a composite FK would, but SET NULL on
    # workspace_id would then asymmetrically clear only part of the pair, so we do
    # not introduce one here). The repository / generation layer MUST verify the
    # match before writing, upholding the "no reaching into other tenants"
    # guarantee (permission-design.md section 3).
    workspace_id: Mapped[int | None] = mapped_column(
        ForeignKey("workspace.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(nullable=False)
    source_uri: Mapped[str | None] = mapped_column(nullable=True)
    # Real-world last-updated date of the source material (distinct from the
    # row's updated_at); drives the stale-source warning for old references.
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    tenant: Mapped[Tenant] = relationship(back_populates="documents")
    workspace: Mapped[Workspace | None] = relationship(back_populates="documents")
    chunks: Mapped[list[Chunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
