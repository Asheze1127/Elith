"""Tests for the ingestion pipeline: split -> embed -> persist.

Covers the DoD for #7: a sample document ingests into tenant-scoped Chunk rows
with the correct embedding dimension, and the exception-shaped failure modes
(empty content / unknown tenant / provider failure) surface clear errors
instead of leaking internals.
"""

from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.chunk import EMBEDDING_DIM, Chunk
from app.providers.base import EmbeddingProvider
from app.repository.documents import TenantNotFoundError
from ingestion.pipeline import EmbeddingProviderError, EmptyDocumentError, ingest_document
from ingestion.splitter import split_text

SAMPLE_DOC_PATH = Path(__file__).resolve().parents[1] / "sample_data" / "shinonome_faq.txt"


class _BoomEmbeddingProvider(EmbeddingProvider):
    """An embedding provider that always fails, for exercising error handling."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("provider unavailable")

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("provider unavailable")


# --- splitter --------------------------------------------------------------


def test_split_text_produces_overlapping_chunks() -> None:
    text = "a" * 120
    chunks = split_text(text, chunk_size=50, overlap=10)
    assert len(chunks) > 1
    # Neighboring chunks share the overlap region.
    assert chunks[0][-10:] == chunks[1][:10]


def test_split_text_empty_input_returns_no_chunks() -> None:
    assert split_text("   ") == []


def test_split_text_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        split_text("hello", chunk_size=10, overlap=10)


# --- pipeline (requires a live DB via conftest fixtures) --------------------


def test_ingest_sample_document_persists_chunks_with_tenant_scope(db_session, make_tenant) -> None:
    tenant = make_tenant("Shinonome Business Support")
    content = SAMPLE_DOC_PATH.read_text(encoding="utf-8")

    document = ingest_document(
        db_session, tenant_id=tenant.id, title="Shinonome FAQ", content=content
    )

    assert document.id is not None
    assert document.tenant_id == tenant.id

    stored_chunks = db_session.scalars(select(Chunk).where(Chunk.document_id == document.id)).all()
    assert len(stored_chunks) > 0
    for chunk in stored_chunks:
        assert chunk.tenant_id == tenant.id
        assert len(chunk.embedding) == EMBEDDING_DIM


def test_ingest_document_rejects_empty_content(db_session, make_tenant) -> None:
    tenant = make_tenant()
    with pytest.raises(EmptyDocumentError):
        ingest_document(db_session, tenant_id=tenant.id, title="Empty", content="   ")


def test_ingest_document_rejects_unknown_tenant(db_session) -> None:
    with pytest.raises(TenantNotFoundError):
        ingest_document(db_session, tenant_id=999_999, title="X", content="hello world")


def test_ingest_document_wraps_provider_failure(db_session, make_tenant) -> None:
    tenant = make_tenant()
    with pytest.raises(EmbeddingProviderError):
        ingest_document(
            db_session,
            tenant_id=tenant.id,
            title="X",
            content="hello world",
            embedding_provider=_BoomEmbeddingProvider(),
        )
