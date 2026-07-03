"""Tests for app.rag.steps.cite (#10): citation drafts + citation-required no-data signal.

Covers the DoD for #10: an answer gets citations attached when chunks exist,
``answer.citation == "required"`` with nothing to cite suppresses a
confident-looking answer by escalating ``status`` to ``STATUS_NO_DATA``
(rather than editing generated text, which does not exist yet when this step
runs -- see cite.py's module docstring for the full reasoning), the same
zero-chunk case with citation NOT required leaves status untouched (proving
the escalation is conditional, not unconditional), multiple chunks produce
one citation each in a stable order, and the step composes correctly through
the real ``run_pipeline`` orchestrator (not just called directly).

Tenant scoping: this step never queries the DB directly (chunk.document is a
lazy relationship load through the same tenant-scoped session retrieve()
already used), so there is no new unscoped access path to prove isolation
for -- see test_tenant_scope.py for the dedicated isolation suite that
covers retrieve() itself.
"""

from datetime import UTC, datetime

from app.models.answer import STATUS_ANSWERED, STATUS_NEEDS_REVIEW, STATUS_NO_DATA
from app.models.chunk import Chunk
from app.models.document import Document
from app.providers import get_embedding_provider
from app.providers.base import LLMProvider
from app.rag.pipeline import run_pipeline
from app.rag.steps import CitationDraft, PipelineState
from app.rag.steps.cite import _SNIPPET_MAX_CHARS, cite


class _StubLLMProvider(LLMProvider):
    """Returns a fixed answer; used where a test only cares about the pipeline state."""

    def generate(self, prompt: str, **opts: object) -> str:
        return "stub answer"


def _seed_chunk(
    db_session,
    *,
    tenant_id: int,
    content: str,
    title: str = "Doc",
    source_uri: str | None = None,
    source_updated_at: datetime | None = None,
) -> tuple[Document, Chunk]:
    """Persist one Document + one Chunk, mirroring test_retrieve.py's pattern."""
    provider = get_embedding_provider()
    vector = provider.embed_query(content)
    document = Document(
        tenant_id=tenant_id,
        title=title,
        source_uri=source_uri,
        source_updated_at=source_updated_at,
    )
    document.chunks = [Chunk(tenant_id=tenant_id, content=content, embedding=vector)]
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document, document.chunks[0]


def test_cite_attaches_citation_with_chunk_and_source_metadata(db_session, make_tenant) -> None:
    tenant = make_tenant()
    source_updated_at = datetime(2024, 1, 15, tzinfo=UTC)
    document, chunk = _seed_chunk(
        db_session,
        tenant_id=tenant.id,
        content="Support hours are 9am-5pm on weekdays.",
        title="FAQ",
        source_uri="https://example.com/faq",
        source_updated_at=source_updated_at,
    )
    state = PipelineState(chunks=[chunk])

    result = cite(state, {})

    assert len(result.citations) == 1
    draft = result.citations[0]
    assert draft.chunk_id == chunk.id
    assert draft.document_id == document.id
    assert draft.snippet == "Support hours are 9am-5pm on weekdays."
    assert draft.source_uri == "https://example.com/faq"
    assert draft.source_updated_at == source_updated_at


def test_cite_truncates_long_chunk_content_to_snippet_max_chars(db_session, make_tenant) -> None:
    tenant = make_tenant()
    long_content = "A" * (_SNIPPET_MAX_CHARS + 50)
    _, chunk = _seed_chunk(db_session, tenant_id=tenant.id, content=long_content)
    state = PipelineState(chunks=[chunk])

    result = cite(state, {})

    snippet = result.citations[0].snippet
    assert snippet.endswith("...")
    assert len(snippet) == _SNIPPET_MAX_CHARS + len("...")


def test_cite_required_with_no_chunks_sets_status_no_data() -> None:
    # No chunks to cite + citation required -> the "no data" signal (see
    # cite.py's module docstring): this is process-flow.md §5.2's "データな
    # し（検索ヒット0）", distinct from §5.1's "根拠不足" (ground_check's
    # territory, for nonzero-but-weak grounding).
    state = PipelineState(chunks=[])

    result = cite(state, {"answer": {"citation": "required"}})

    assert result.status == STATUS_NO_DATA
    assert result.citations == []


def test_cite_not_required_with_no_chunks_does_not_force_status() -> None:
    # Contrast case: proves the no-data escalation is conditional on
    # answer.citation == "required", not an unconditional "no chunks" rule.
    state = PipelineState(chunks=[])

    result_optional = cite(state, {"answer": {"citation": "optional"}})
    assert result_optional.status == STATUS_ANSWERED

    result_absent = cite(state, {})
    assert result_absent.status == STATUS_ANSWERED

    # Defensive shape handling: a mis-seeded "answer" that isn't a dict must
    # not raise or be treated as citation-required.
    result_malformed = cite(state, {"answer": "external"})
    assert result_malformed.status == STATUS_ANSWERED


def test_cite_never_loosens_an_already_worse_status() -> None:
    # cite must never loosen a status a previous step already set to
    # something worse than its own candidate (escalate_status's "tighten
    # only" rule, shared with ground_check -- see cite.py's module
    # docstring). STATUS_NO_DATA is already the most severe outcome, so
    # cite's own zero-chunks/citation-required candidate (also NO_DATA)
    # must leave it exactly as-is, not "reset" it.
    state = PipelineState(chunks=[], status=STATUS_NO_DATA)

    result = cite(state, {"answer": {"citation": "required"}})

    assert result.status == STATUS_NO_DATA


def test_cite_tightens_a_less_severe_status_to_no_data() -> None:
    # Escalation must go the other way too: a prior step's STATUS_NEEDS_REVIEW
    # is LESS severe than what cite would independently conclude (zero chunks
    # + citation required -> STATUS_NO_DATA), so cite must tighten it up to
    # NO_DATA rather than leaving the weaker verdict in place -- this is the
    # "escalate_status is symmetric with ground_check" guarantee the shared
    # helper exists to provide (see cite.py's module docstring).
    state = PipelineState(chunks=[], status=STATUS_NEEDS_REVIEW)

    result = cite(state, {"answer": {"citation": "required"}})

    assert result.status == STATUS_NO_DATA


def test_cite_produces_one_citation_per_chunk_in_order(db_session, make_tenant) -> None:
    tenant = make_tenant()
    provider = get_embedding_provider()
    document = Document(tenant_id=tenant.id, title="Multi-chunk doc")
    document.chunks = [
        Chunk(
            tenant_id=tenant.id,
            content=f"chunk {i}",
            embedding=provider.embed_query(f"chunk {i}"),
        )
        for i in range(3)
    ]
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    state = PipelineState(chunks=document.chunks)

    result = cite(state, {})

    assert [d.chunk_id for d in result.citations] == [c.id for c in document.chunks]
    assert [d.snippet for d in result.citations] == ["chunk 0", "chunk 1", "chunk 2"]


def test_cite_appends_to_existing_citations_without_overwriting(db_session, make_tenant) -> None:
    tenant = make_tenant()
    _, chunk = _seed_chunk(db_session, tenant_id=tenant.id, content="new content")
    existing = CitationDraft(chunk_id=999, snippet="already here")
    state = PipelineState(chunks=[chunk], citations=[existing])

    result = cite(state, {})

    assert result.citations[0] is existing
    assert len(result.citations) == 2
    assert result.citations[1].chunk_id == chunk.id


def test_cite_does_not_mutate_input_state(db_session, make_tenant) -> None:
    tenant = make_tenant()
    _, chunk = _seed_chunk(db_session, tenant_id=tenant.id, content="content")
    state = PipelineState(chunks=[chunk])

    cite(state, {})

    # The original PipelineState passed in must be untouched (step contract:
    # return a NEW PipelineState, never mutate the input).
    assert state.citations == []
    assert state.status == STATUS_ANSWERED


def test_cite_runs_through_run_pipeline_end_to_end(db_session, make_tenant) -> None:
    tenant = make_tenant()
    _, chunk = _seed_chunk(db_session, tenant_id=tenant.id, content="hours are 9 to 5")

    result = run_pipeline(
        db_session,
        tenant_id=tenant.id,
        query="hours are 9 to 5",
        config={"pipeline": ["cite"]},
        llm_provider=_StubLLMProvider(),
    )

    assert result.answer == "stub answer"
    assert len(result.citations) == 1
    assert result.citations[0].chunk_id == chunk.id
    assert result.citations[0].document_id == chunk.document_id


def test_cite_runs_through_run_pipeline_no_data_when_citation_required(
    db_session, make_tenant
) -> None:
    tenant = make_tenant()  # no documents/chunks seeded -> retrieve() returns []

    result = run_pipeline(
        db_session,
        tenant_id=tenant.id,
        query="a question with no matching documents",
        config={"answer": {"citation": "required"}, "pipeline": ["cite"]},
        llm_provider=_StubLLMProvider(),
    )

    assert result.chunks == []
    assert result.citations == []
    assert result.status == STATUS_NO_DATA
