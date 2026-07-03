"""Chunk: a slice of a document plus its embedding vector.

The embedding column uses pgvector. Retrieval does a tenant-scoped nearest-
neighbor search over ``embedding`` using cosine distance (tech-stack.md §4,
app.rag.retrieve, settled in #8). An ANN index (ivfflat / hnsw, both of which
support a cosine op class) can be added later once data volume warrants it;
it is left out of the initial migration on purpose -- an index over a table
this small (MVP-scale fixture/demo data) gives no benefit and an
approximate-nearest-neighbor index would only add recall risk before there is
data to tune it against.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models._common import TimestampMixin

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.tenant import Tenant

# Gemini text-embedding-004 output dimension. Must match the Embedding
# provider; changing the provider/model means changing this and re-embedding.
EMBEDDING_DIM = 768


class Chunk(TimestampMixin, Base):
    __tablename__ = "chunk"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Denormalized tenant_id so every chunk is directly tenant-scopable without
    # a join back through document (permission-design.md §3: scope all queries).
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)

    tenant: Mapped[Tenant] = relationship(back_populates="chunks")
    document: Mapped[Document] = relationship(back_populates="chunks")
