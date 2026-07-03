"""Ingestion pipeline orchestrator: split -> embed -> persist.

This is a shared, tenant-agnostic pipeline part (multi-tenant-design.md): the
same code path runs for every tenant; only ``tenant_id`` / ``workspace_id``
(data) differ per call. Embedding goes exclusively through the Provider
abstraction (``app.providers``), never a concrete SDK, so the pipeline works
unchanged whether the real Gemini provider or the network-free mock is
selected (process-flow.md §3).
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.document import Document
from app.providers import get_embedding_provider
from app.providers.base import EmbeddingProvider
from app.repository import documents as documents_repo
from ingestion.splitter import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, split_text


class IngestionError(Exception):
    """Base class for recoverable ingestion failures with a user-facing message."""


class EmptyDocumentError(IngestionError):
    """Raised when the document has no non-whitespace content to ingest."""


class EmbeddingProviderError(IngestionError):
    """Raised when the embedding provider fails to embed the document chunks.

    Wraps the underlying provider/SDK exception so callers (the API layer) can
    return a clear message without leaking a raw stack trace or SDK internals.
    """


def ingest_document(
    db: Session,
    *,
    tenant_id: int,
    title: str,
    content: str,
    workspace_id: int | None = None,
    source_uri: str | None = None,
    source_updated_at: datetime | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    embedding_provider: EmbeddingProvider | None = None,
) -> Document:
    """Split ``content``, embed the chunks, and persist Document + Chunk rows.

    Raises ``EmptyDocumentError`` / ``EmbeddingProviderError`` (this module) or
    ``TenantNotFoundError`` / ``WorkspaceMismatchError``
    (``app.repository.documents``) -- all carry a message safe to show to the
    caller. Nothing is written to the DB before the tenant/workspace scope is
    validated (see ``documents_repo.create_document``).
    """
    chunks = split_text(content, chunk_size=chunk_size, overlap=chunk_overlap)
    if not chunks:
        raise EmptyDocumentError("document content must not be empty")

    provider = embedding_provider or get_embedding_provider()
    try:
        embeddings = provider.embed_documents(chunks)
    except Exception as exc:  # provider/SDK errors vary; normalize to one type
        raise EmbeddingProviderError(f"failed to generate embeddings: {exc}") from exc

    # A provider returning a different number of vectors than input chunks is
    # a contract violation, not a caller input error; catch it here (as an
    # EmbeddingProviderError -> 502) instead of letting it surface as an
    # unhandled ValueError from the strict zip() in create_document.
    if len(embeddings) != len(chunks):
        raise EmbeddingProviderError(
            f"embedding provider returned {len(embeddings)} vectors for {len(chunks)} chunks"
        )

    return documents_repo.create_document(
        db,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        title=title,
        source_uri=source_uri,
        source_updated_at=source_updated_at,
        chunk_texts=chunks,
        chunk_embeddings=embeddings,
    )
