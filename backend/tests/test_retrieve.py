"""Tests for app.rag.retrieve: tenant-scoped nearest-neighbor search (#8).

Covers the DoD for #8: a query returns relevant chunks, an embedding-provider
failure surfaces a clear wrapped exception, a tenant with no chunks yields an
empty (non-error) result, and workspace-scoped retrieval excludes chunks from
other workspaces in the same tenant. The cross-tenant isolation guarantee --
the most important property of this module -- has its own dedicated,
adversarial test suite in test_tenant_scope.py; this file only sanity-checks
that a second tenant's chunk is not returned by a basic query.
"""

import pytest
from sqlalchemy import select

from app.models.chunk import EMBEDDING_DIM, Chunk
from app.models.document import Document
from app.models.workspace import Workspace
from app.providers import get_embedding_provider
from app.providers.base import EmbeddingProvider
from app.rag.retrieve import EmbeddingProviderError, retrieve


class _BoomEmbeddingProvider(EmbeddingProvider):
    """An embedding provider that always fails, for exercising error handling."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("provider unavailable")

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("provider unavailable")


def _add_document_with_chunks(
    db_session,
    *,
    tenant_id: int,
    title: str,
    chunks: list[tuple[str, list[float]]],
    workspace_id=None,
) -> Document:
    """Directly persist a Document + Chunk rows with caller-chosen embeddings.

    Bypasses the ingestion pipeline so tests can pin exact embedding vectors
    (needed to make retrieval ordering/scoping assertions deterministic).
    """
    document = Document(tenant_id=tenant_id, workspace_id=workspace_id, title=title)
    document.chunks = [
        Chunk(tenant_id=tenant_id, content=text, embedding=embedding) for text, embedding in chunks
    ]
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def test_retrieve_returns_relevant_chunk_for_tenant_query(db_session, make_tenant) -> None:
    tenant = make_tenant()
    provider = get_embedding_provider()
    query = "how do I reset my password"
    # Pin the chunk's embedding to exactly what the query embeds to, so it is
    # guaranteed to be the nearest neighbor regardless of the (mock) provider's
    # internals -- the test only needs to know retrieve() surfaces it.
    matching_vector = provider.embed_query(query)
    document = _add_document_with_chunks(
        db_session,
        tenant_id=tenant.id,
        title="FAQ",
        chunks=[("reset your password from the settings page", matching_vector)],
    )

    results = retrieve(db_session, tenant_id=tenant.id, query=query)

    assert len(results) == 1
    assert results[0].id == document.chunks[0].id
    assert results[0].tenant_id == tenant.id


def test_retrieve_orders_by_distance_nearest_first(db_session, make_tenant) -> None:
    tenant = make_tenant()
    provider = get_embedding_provider()
    query = "billing question"
    near_vector = provider.embed_query(query)
    # A vector far from the query in every dimension (near_vector is scaled to
    # [0, 1) by the mock provider -- see app.providers.mock -- so 1.0 - x pushes
    # every dimension to the opposite end of that range, maximizing cosine
    # distance from near_vector for a non-degenerate vector).
    far_vector = [1.0 - x for x in near_vector]
    document = _add_document_with_chunks(
        db_session,
        tenant_id=tenant.id,
        title="Mixed relevance",
        chunks=[("far chunk", far_vector), ("near chunk", near_vector)],
    )
    far_chunk, near_chunk = document.chunks

    results = retrieve(db_session, tenant_id=tenant.id, query=query, top_k=2)

    assert [c.id for c in results] == [near_chunk.id, far_chunk.id]


def test_retrieve_returns_empty_list_when_tenant_has_no_chunks(db_session, make_tenant) -> None:
    tenant = make_tenant()

    results = retrieve(db_session, tenant_id=tenant.id, query="anything")

    assert results == []


def test_retrieve_wraps_embedding_provider_failure(db_session, make_tenant) -> None:
    tenant = make_tenant()

    with pytest.raises(EmbeddingProviderError):
        retrieve(
            db_session,
            tenant_id=tenant.id,
            query="anything",
            embedding_provider=_BoomEmbeddingProvider(),
        )


def test_retrieve_rejects_non_positive_top_k(db_session, make_tenant) -> None:
    tenant = make_tenant()

    with pytest.raises(ValueError):
        retrieve(db_session, tenant_id=tenant.id, query="anything", top_k=0)


def test_retrieve_workspace_scope_excludes_other_workspace_chunks(db_session, make_tenant) -> None:
    tenant = make_tenant()
    workspace_a = Workspace(tenant_id=tenant.id, name="Dept A")
    workspace_b = Workspace(tenant_id=tenant.id, name="Dept B")
    db_session.add_all([workspace_a, workspace_b])
    db_session.commit()
    db_session.refresh(workspace_a)
    db_session.refresh(workspace_b)

    provider = get_embedding_provider()
    query = "shared question"
    vector = provider.embed_query(query)
    doc_a = _add_document_with_chunks(
        db_session,
        tenant_id=tenant.id,
        title="Dept A doc",
        chunks=[("dept A content", vector)],
        workspace_id=workspace_a.id,
    )
    doc_b = _add_document_with_chunks(
        db_session,
        tenant_id=tenant.id,
        title="Dept B doc",
        chunks=[("dept B content", vector)],
        workspace_id=workspace_b.id,
    )

    results = retrieve(db_session, tenant_id=tenant.id, query=query, workspace_id=workspace_a.id)

    result_ids = {c.id for c in results}
    assert doc_a.chunks[0].id in result_ids
    assert doc_b.chunks[0].id not in result_ids


def test_retrieve_basic_second_tenant_chunk_not_returned(db_session, make_tenant) -> None:
    # Basic sanity check colocated with the rest of retrieve()'s behavior tests;
    # see test_tenant_scope.py for the dedicated, adversarial isolation suite.
    tenant_a = make_tenant("Tenant A")
    tenant_b = make_tenant("Tenant B")
    provider = get_embedding_provider()
    query = "generic question"
    vector = provider.embed_query(query)

    _add_document_with_chunks(
        db_session, tenant_id=tenant_a.id, title="A doc", chunks=[("A content", vector)]
    )
    _add_document_with_chunks(
        db_session, tenant_id=tenant_b.id, title="B doc", chunks=[("B content", vector)]
    )

    results = retrieve(db_session, tenant_id=tenant_a.id, query=query)

    assert all(c.tenant_id == tenant_a.id for c in results)
    assert all("B content" != c.content for c in results)


def test_retrieve_reads_only_via_orm_no_leftover_rows(db_session, make_tenant) -> None:
    # Regression guard: retrieve() must not write anything (read-only).
    tenant = make_tenant()
    before = db_session.scalars(select(Chunk)).all()

    retrieve(db_session, tenant_id=tenant.id, query="anything")

    after = db_session.scalars(select(Chunk)).all()
    assert len(before) == len(after)
    assert EMBEDDING_DIM == 768
