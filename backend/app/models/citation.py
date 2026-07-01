"""Citation: a source that an answer referenced.

Boundary note (permission-design.md §3): the citation boundary is
``citation.answer_id`` -- a citation is reachable (and therefore tenant-scopable)
only through its answer. We deliberately do NOT add a direct ``tenant_id`` here,
because the design defines the citation boundary as "the materials the answer
referenced", i.e. via the answer. Adding a redundant tenant_id would risk it
diverging from answer.tenant_id.

``chunk_id`` and ``document_id`` are both nullable: a citation may point at a
specific chunk, at a whole document, or (for a snapshot) keep only the copied
snippet/source_uri even if the underlying row is later removed.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models._common import TimestampMixin

if TYPE_CHECKING:
    from app.models.answer import Answer


class Citation(TimestampMixin, Base):
    __tablename__ = "citation"

    id: Mapped[int] = mapped_column(primary_key=True)
    answer_id: Mapped[int] = mapped_column(
        ForeignKey("answer.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Nullable: cite a specific chunk when available; SET NULL keeps the citation
    # (with its snapshot snippet) if the chunk/document is later deleted.
    #
    # Same-tenant invariant: the referenced chunk / document MUST belong to the
    # same tenant as this citation's answer, i.e. chunk.tenant_id ==
    # answer.tenant_id and document.tenant_id == answer.tenant_id. Citation carries
    # no tenant_id of its own -- it is scoped through its answer by design (see the
    # module docstring) -- so the DB cannot enforce this. The repository /
    # generation layer MUST verify the same-tenant match before writing.
    chunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("chunk.id", ondelete="SET NULL"),
        nullable=True,
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("document.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Copied text/metadata so the citation stays displayable independent of the
    # source row (show_source_metadata in tenant_config).
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_uri: Mapped[str | None] = mapped_column(nullable=True)
    # Source's last-updated date, surfaced to the user for stale-source warnings.
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    answer: Mapped[Answer] = relationship(back_populates="citations")
