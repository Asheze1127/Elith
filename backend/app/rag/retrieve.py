"""Tenant-scoped nearest-neighbor retrieval over ``Chunk.embedding`` (#8).

This is the single most important security guarantee in the product
(permission-design.md section 3: "other tenants' rows are never reached").
Every query here filters by ``Chunk.tenant_id`` first and unconditionally --
never leave that filter to be composed in by a caller. An optional
``workspace_id`` narrows the search further within the tenant, mirroring
``tenant_config.search.scope`` (multi-tenant-design.md); it is data (a
parameter), never a per-tenant code branch.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.document import Document
from app.providers import get_embedding_provider
from app.providers.base import EmbeddingProvider

# A small, fixed top-k keeps the downstream prompt (later issues: #9-#11) short
# and fast to build while still giving the answer step enough context; 5 is a
# common default for RAG retrieval. Tune later once real answer quality data
# exists.
DEFAULT_TOP_K = 5


class RetrieveError(Exception):
    """Base class for recoverable retrieval failures with a user-facing message."""


class EmbeddingProviderError(RetrieveError):
    """Raised when the embedding provider fails to embed the query text.

    Wraps the underlying provider/SDK exception (mirrors
    ``ingestion.pipeline.EmbeddingProviderError``) so callers (the API/pipeline
    layer) can surface a clear message without leaking a raw stack trace or SDK
    internals (process-flow.md section 5.3).
    """


def retrieve(
    db: Session,
    *,
    tenant_id: int,
    query: str,
    workspace_id: int | None = None,
    top_k: int = DEFAULT_TOP_K,
    embedding_provider: EmbeddingProvider | None = None,
) -> list[Chunk]:
    """Return the top-k chunks nearest ``query``, scoped to ``tenant_id``.

    Every chunk returned belongs to ``tenant_id``; this filter is applied
    unconditionally and first (permission-design.md section 3). When
    ``workspace_id`` is given, results are further narrowed to chunks whose
    document belongs to that workspace (mirrors ``tenant_config.search.scope``).
    ``Chunk`` carries no ``workspace_id`` of its own (see app.models.chunk), so
    this requires a join to ``Document``.

    A tenant with no chunks yet -- or a workspace with no matching documents --
    is not an error: an empty list is returned (process-flow.md section 5.2,
    "no data found" is a normal, user-facing outcome). Only a query-embedding
    failure raises (``EmbeddingProviderError``); an invalid ``top_k`` raises
    ``ValueError`` (a caller/programming error, not a runtime condition to wrap).
    """
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    provider = embedding_provider or get_embedding_provider()
    try:
        query_vector = provider.embed_query(query)
    except Exception as exc:  # provider/SDK errors vary; normalize to one type
        raise EmbeddingProviderError(f"failed to embed query: {exc}") from exc

    # Cosine distance is the standard similarity metric for text embeddings --
    # direction matters, magnitude doesn't -- and matches how Gemini's
    # text-embedding-004 (and the deterministic mock, which mirrors its shape)
    # is meant to be compared. pgvector exposes it as a comparator method on the
    # mapped Vector column, compiling to the `<=>` operator.
    distance = Chunk.embedding.cosine_distance(query_vector)

    stmt = select(Chunk).where(Chunk.tenant_id == tenant_id)
    if workspace_id is not None:
        # Document.tenant_id is included in the join condition even though
        # Chunk.tenant_id is already filtered above: never rely on a single
        # unscoped/half-scoped filter for the tenant boundary (this is the
        # module's primary contract). A workspace_id that belongs to a
        # different tenant then simply matches nothing, rather than widening
        # the result set to another tenant's data.
        stmt = stmt.join(Document, Document.id == Chunk.document_id).where(
            Document.tenant_id == tenant_id,
            Document.workspace_id == workspace_id,
        )
    stmt = stmt.order_by(distance).limit(top_k)

    return list(db.scalars(stmt).all())
