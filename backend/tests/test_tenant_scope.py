"""Dedicated tenant-isolation test suite (directory.md's test structure template:
"other tenants' data is never reached").

This file exists to hold the single most scrutinized guarantee in the product
(permission-design.md section 3): a query scoped to tenant A must never surface
tenant B's rows, no matter how the query is constructed. #8 [BE-06] retrieve is
the first read path where this matters against a live DB (previously,
test_models_scope.py only checked schema/metadata shape, never real query
behavior), so its adversarial tests live here first; later issues (pipeline,
chat, citations, ...) should add their own tenant-isolation cases to this file
rather than scattering them across feature test files.
"""

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.workspace import Workspace
from app.providers import get_embedding_provider
from app.providers.base import LLMProvider
from app.rag.pipeline import run_pipeline
from app.rag.retrieve import retrieve


def _seed_document(
    db_session, *, tenant_id: int, title: str, content: str, embedding, workspace_id=None
):
    document = Document(tenant_id=tenant_id, workspace_id=workspace_id, title=title)
    document.chunks = [Chunk(tenant_id=tenant_id, content=content, embedding=embedding)]
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def test_retrieve_never_returns_another_tenants_chunks(db_session, make_tenant) -> None:
    """Adversarial cross-tenant isolation test -- the primary DoD item for #8.

    Setup deliberately stacks the deck *against* isolation holding: tenant B's
    chunk embedding is pinned to the exact query embedding (cosine distance 0,
    i.e. the best possible nearest-neighbor match against any tenant's data),
    while tenant A's own chunk is an unrelated, generic vector. If retrieve()
    ever failed to scope by tenant_id -- e.g. an unfiltered ORDER BY distance
    query, or a filter that only *sorts* by tenant instead of restricting to
    it -- tenant B's chunk would be the #1 result returned to tenant A. It
    must not appear at all, regardless of top_k or how broad/generic the query
    text is.
    """
    tenant_a = make_tenant("Tenant A")
    tenant_b = make_tenant("Tenant B")
    provider = get_embedding_provider()

    # A deliberately generic/broad query -- the kind most likely to match
    # broadly across many tenants' documents if scoping were ever broken.
    broad_query = "please help me"
    adversarial_vector = provider.embed_query(broad_query)

    # Tenant A: an ordinary, unrelated chunk (no relation to the query).
    chunk_a_doc = _seed_document(
        db_session,
        tenant_id=tenant_a.id,
        title="A's internal doc",
        content="how to submit an expense report",
        embedding=provider.embed_query("how to submit an expense report"),
    )

    # Tenant B: a chunk engineered to be the closest possible match to the
    # query -- the adversarial case. It must never come back for tenant A.
    chunk_b_doc = _seed_document(
        db_session,
        tenant_id=tenant_b.id,
        title="B's confidential doc",
        content="TENANT B SECRET: internal salary bands",
        embedding=adversarial_vector,
    )

    # Ask for many neighbors so "it just fell outside top_k" cannot explain
    # an absence -- if tenant scoping were broken, B's perfect-match chunk
    # would rank #1 and easily fit within this top_k.
    results = retrieve(db_session, tenant_id=tenant_a.id, query=broad_query, top_k=50)

    result_ids = {c.id for c in results}
    result_contents = {c.content for c in results}

    assert chunk_b_doc.chunks[0].id not in result_ids
    assert "TENANT B SECRET: internal salary bands" not in result_contents
    assert all(c.tenant_id == tenant_a.id for c in results)
    # Sanity: tenant A's own (unrelated) chunk is still reachable -- this is
    # not just an empty-result false-positive.
    assert chunk_a_doc.chunks[0].id in result_ids


def test_retrieve_ignores_workspace_id_belonging_to_another_tenant(db_session, make_tenant) -> None:
    """A workspace_id that collides with another tenant's workspace must not leak it.

    Simulates a caller bug/attack where tenant A's request carries a
    workspace_id that (by primary-key coincidence or a forged request) belongs
    to tenant B. The join in retrieve() requires Document.tenant_id ==
    tenant_id AND Document.workspace_id == workspace_id simultaneously, so a
    workspace_id owned by another tenant can never match any of tenant A's
    documents -- the result must be empty, not tenant B's data.
    """
    tenant_a = make_tenant("Tenant A")
    tenant_b = make_tenant("Tenant B")
    workspace_b = Workspace(tenant_id=tenant_b.id, name="B's department")
    db_session.add(workspace_b)
    db_session.commit()
    db_session.refresh(workspace_b)

    provider = get_embedding_provider()
    query = "generic scoped query"
    vector = provider.embed_query(query)

    # Tenant A has chunks, but none in any workspace (tenant-wide documents).
    _seed_document(
        db_session, tenant_id=tenant_a.id, title="A doc", content="A content", embedding=vector
    )
    # Tenant B's workspace has a real, matching document/chunk.
    _seed_document(
        db_session,
        tenant_id=tenant_b.id,
        title="B doc",
        content="B content",
        embedding=vector,
        workspace_id=workspace_b.id,
    )

    # Tenant A's request "coincidentally" carries tenant B's workspace_id.
    results = retrieve(db_session, tenant_id=tenant_a.id, query=query, workspace_id=workspace_b.id)

    assert results == []


def test_retrieve_workspace_join_rejects_document_owned_by_another_tenant(
    db_session, make_tenant
) -> None:
    """Defense-in-depth check for the Document.tenant_id condition in the
    workspace-scoped join (retrieve.py), independent of the top-level
    Chunk.tenant_id filter.

    There is no DB-level constraint tying Chunk.tenant_id to its Document's
    tenant_id (a documented, deliberate gap from #3's boundary design), so a
    Chunk row inconsistent with its Document is a schema-permitted state, not
    a hypothetical. This test constructs exactly that inconsistency directly
    (bypassing the ingestion/#7 repository layer, which would normally
    prevent it) to prove retrieve() would still refuse to leak the document
    even if such a row existed: a chunk tagged tenant_id=A but attached to a
    Document owned by tenant B must NOT come back for tenant A's
    workspace-scoped query, because the join also requires
    Document.tenant_id == tenant_id -- not just the workspace_id match.
    """
    tenant_a = make_tenant("Tenant A")
    tenant_b = make_tenant("Tenant B")
    workspace_b = Workspace(tenant_id=tenant_b.id, name="B's department")
    db_session.add(workspace_b)
    db_session.commit()
    db_session.refresh(workspace_b)

    provider = get_embedding_provider()
    query = "generic scoped query"
    vector = provider.embed_query(query)

    # Document genuinely owned by tenant B, in B's workspace.
    document_b = Document(tenant_id=tenant_b.id, workspace_id=workspace_b.id, title="B doc")
    # Inconsistent chunk: tagged as tenant A's, but attached to B's document.
    # Schema-permitted (no composite FK enforces this), so retrieve() alone
    # must be the safeguard.
    document_b.chunks = [Chunk(tenant_id=tenant_a.id, content="B content", embedding=vector)]
    db_session.add(document_b)
    db_session.commit()

    results = retrieve(db_session, tenant_id=tenant_a.id, query=query, workspace_id=workspace_b.id)

    assert results == []


def test_retrieve_never_returns_another_tenants_chunks_when_tenant_has_no_data(
    db_session, make_tenant
) -> None:
    """A tenant with zero chunks of its own must get an empty result, never a
    fallback into another tenant's data (empty is a valid, non-error outcome:
    process-flow.md section 5.2)."""
    tenant_a = make_tenant("Tenant A (empty)")
    tenant_b = make_tenant("Tenant B (has data)")
    provider = get_embedding_provider()
    query = "anything at all"

    _seed_document(
        db_session,
        tenant_id=tenant_b.id,
        title="B doc",
        content="B content",
        embedding=provider.embed_query(query),
    )

    results = retrieve(db_session, tenant_id=tenant_a.id, query=query)

    assert results == []


class _StubLLMProvider(LLMProvider):
    """Fixed-answer provider; these tests only care about which chunks
    reached the prompt, not the pipeline's answer text."""

    def generate(self, prompt: str, **opts: object) -> str:
        return "stub answer"


def test_run_pipeline_never_returns_another_tenants_chunks(db_session, make_tenant) -> None:
    """#9's orchestrator (app.rag.pipeline.run_pipeline) must forward
    tenant_id to retrieve() unchanged, never widening or bypassing its
    tenant scoping.

    This is NOT a re-test of retrieve()'s own isolation guarantee -- that is
    already exhaustively covered above -- it only confirms run_pipeline's
    call into retrieve() stays scoped, using the same adversarial setup
    (tenant B's chunk pinned to the best possible match for tenant A's query).
    """
    tenant_a = make_tenant("Tenant A")
    tenant_b = make_tenant("Tenant B")
    provider = get_embedding_provider()
    broad_query = "please help me"
    adversarial_vector = provider.embed_query(broad_query)

    chunk_a_doc = _seed_document(
        db_session,
        tenant_id=tenant_a.id,
        title="A's doc",
        content="how to submit an expense report",
        embedding=provider.embed_query("how to submit an expense report"),
    )
    chunk_b_doc = _seed_document(
        db_session,
        tenant_id=tenant_b.id,
        title="B's confidential doc",
        content="TENANT B SECRET: internal salary bands",
        embedding=adversarial_vector,
    )

    result = run_pipeline(
        db_session,
        tenant_id=tenant_a.id,
        query=broad_query,
        config={"pipeline": []},
        top_k=50,
        llm_provider=_StubLLMProvider(),
    )

    result_ids = {c.id for c in result.chunks}
    assert chunk_b_doc.chunks[0].id not in result_ids
    assert all(c.tenant_id == tenant_a.id for c in result.chunks)
    assert chunk_a_doc.chunks[0].id in result_ids
