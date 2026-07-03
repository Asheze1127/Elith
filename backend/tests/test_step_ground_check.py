"""Tests for app.rag.steps.ground_check (#11): weak-grounding -> needs_review.

Covers the DoD for #11:
- a question with thin evidence (below MIN_GROUNDING_CHUNKS) ends up
  ``needs_review``;
- the changed area's tests/linter pass;
- (exception-side note) this step has no failure mode that would produce a
  user-facing message -- see ground_check.py's module docstring's
  "Exceptions" section for why -- so there is no exception test here.

Also covers the two design decisions the issue asked to document explicitly:
zero chunks maps to a *different*, stronger status (STATUS_NO_DATA,
process-flow.md §5.2) than "some but too few" chunks (STATUS_NEEDS_REVIEW,
§5.1), and this step only ever tightens an already-set status, never loosens
one a hypothetical earlier step already set worse.
"""

import dataclasses

from app.models.answer import STATUS_ANSWERED, STATUS_NEEDS_REVIEW, STATUS_NO_DATA
from app.models.chunk import EMBEDDING_DIM, Chunk
from app.models.document import Document
from app.providers import get_embedding_provider
from app.rag.pipeline import run_pipeline
from app.rag.steps import PipelineState
from app.rag.steps.ground_check import MIN_GROUNDING_CHUNKS, ground_check


class _StubLLMProvider:
    """Returns a fixed answer; the integration tests below only care about status."""

    def generate(self, prompt: str, **opts: object) -> str:
        return "stub answer"


def _make_chunk(content: str = "chunk content") -> Chunk:
    """An in-memory (never persisted) Chunk -- ground_check only reads len(), not DB state."""
    return Chunk(tenant_id=1, document_id=1, content=content, embedding=[0.0] * EMBEDDING_DIM)


# --- Pure-logic unit tests (no DB needed: ground_check does no querying) ----


def test_ground_check_zero_chunks_sets_no_data() -> None:
    # process-flow.md §5.2 ("データなし", zero search hits) is the precise match
    # for "zero chunks retrieved at all" -- distinct from and stronger than
    # §5.1's "some evidence, but thin" case, which STATUS_NEEDS_REVIEW covers
    # (see the next test). Reserving STATUS_NO_DATA for true-zero keeps the two
    # process-flow.md outcomes from being conflated into one status value.
    state = PipelineState(chunks=[])

    result = ground_check(state, {})

    assert result.status == STATUS_NO_DATA


def test_ground_check_few_chunks_sets_needs_review() -> None:
    # Below MIN_GROUNDING_CHUNKS (2): some material exists, but a single,
    # uncorroborated chunk is exactly process-flow.md §5.1's "根拠不足" case.
    # Empty config -> falls back to the default STATUS_NEEDS_REVIEW (see the
    # next test for the config-driven case).
    assert MIN_GROUNDING_CHUNKS == 2
    state = PipelineState(chunks=[_make_chunk()])

    result = ground_check(state, {})

    assert result.status == STATUS_NEEDS_REVIEW


def test_ground_check_weak_grounding_uses_configured_low_confidence_action() -> None:
    # multi-tenant-design.md §3: "low_confidence_action" is tenant_config
    # DATA, not a hardcoded outcome -- a tenant can set it to any status
    # string, and this step must use exactly that value for the "some but
    # too few chunks" case (not silently default to needs_review).
    state = PipelineState(chunks=[_make_chunk()])
    config = {"answer": {"low_confidence_action": "escalate_to_human"}}

    result = ground_check(state, config)

    assert result.status == "escalate_to_human"


def test_ground_check_malformed_answer_config_falls_back_to_default() -> None:
    # config is unvalidated tenant JSONB; a non-dict "answer" section must
    # not raise, and falls back to the same default as an empty config.
    state = PipelineState(chunks=[_make_chunk()])

    result = ground_check(state, {"answer": "external"})

    assert result.status == STATUS_NEEDS_REVIEW


def test_ground_check_enough_chunks_leaves_status_answered() -> None:
    state = PipelineState(chunks=[_make_chunk("a"), _make_chunk("b")])
    assert len(state.chunks) >= MIN_GROUNDING_CHUNKS

    result = ground_check(state, {})

    # Explicitly the default, not just "not needs_review".
    assert result.status == STATUS_ANSWERED


def test_ground_check_never_loosens_an_already_worse_status() -> None:
    # A hypothetical earlier step already decided STATUS_NO_DATA (the worse of
    # the two non-default statuses). Even though this step's own chunk-count
    # check would say "fine" (enough chunks -> would leave status alone /
    # imply STATUS_ANSWERED), ground_check must not loosen the status back up.
    state = dataclasses.replace(
        PipelineState(chunks=[_make_chunk("a"), _make_chunk("b"), _make_chunk("c")]),
        status=STATUS_NO_DATA,
    )
    assert len(state.chunks) >= MIN_GROUNDING_CHUNKS

    result = ground_check(state, {})

    assert result.status == STATUS_NO_DATA


def test_ground_check_does_not_mutate_chunks_or_citations() -> None:
    chunks = [_make_chunk("a")]
    state = PipelineState(chunks=chunks)

    result = ground_check(state, {})

    assert result.chunks is state.chunks
    assert result.citations == []


# --- Integration: through the real orchestrator, with seeded DB rows --------


def test_ground_check_via_run_pipeline_sets_no_data_with_zero_chunks(
    db_session, make_tenant
) -> None:
    tenant = make_tenant()  # no documents/chunks seeded -> retrieve() returns []

    result = run_pipeline(
        db_session,
        tenant_id=tenant.id,
        query="a question with no matching documents",
        config={"pipeline": ["ground_check"]},
        llm_provider=_StubLLMProvider(),
    )

    assert result.chunks == []
    assert result.status == STATUS_NO_DATA


def test_ground_check_via_run_pipeline_leaves_status_answered_with_enough_chunks(
    db_session, make_tenant
) -> None:
    tenant = make_tenant()
    provider = get_embedding_provider()
    query = "how do I reset my password"
    matching_vector = provider.embed_query(query)
    document = Document(tenant_id=tenant.id, title="FAQ")
    document.chunks = [
        Chunk(
            tenant_id=tenant.id,
            content="reset your password from the settings page",
            embedding=matching_vector,
        ),
        Chunk(
            tenant_id=tenant.id,
            content="password resets also work via the mobile app",
            embedding=matching_vector,
        ),
    ]
    db_session.add(document)
    db_session.commit()

    result = run_pipeline(
        db_session,
        tenant_id=tenant.id,
        query=query,
        config={"pipeline": ["ground_check"]},
        llm_provider=_StubLLMProvider(),
    )

    assert len(result.chunks) >= MIN_GROUNDING_CHUNKS
    assert result.status == STATUS_ANSWERED
