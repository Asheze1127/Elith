"""Tests for app.rag.pipeline.run_pipeline (#9): orchestration mechanism only.

Covers the DoD for #9: steps named in config["pipeline"] run in the exact
order given (an order-sensitive assertion, not just "both ran"), an
unregistered step name raises a clear, typed exception naming it, a literal
"retrieve" entry in config["pipeline"] (multi-tenant-design.md §3's sample
config) is a documented no-op rather than an error, an LLM provider failure
is wrapped the same way ingestion/retrieve wrap provider failures, and a step
can set answer-level status/warnings/citations even with zero chunks (the
scenario that motivated widening the step contract from a bare chunk list to
``PipelineState`` -- see app/rag/steps/__init__.py's docstring).

Test-double steps are registered here, in this file only -- product code must
not contain placeholder cite/ground_check/stale_warning/contradiction_check
implementations (see the issue's scope notes). These step names are
deliberately test-only (`_test_*`) and never collide with a real catalog
name; the `_register_test_steps` fixture below registers/deregisters them
around each test so they never leak into the shared, module-global `STEPS`
registry.

Cross-tenant isolation of run_pipeline's retrieve() call has its own case in
test_tenant_scope.py (that file's docstring asks later issues to add their
isolation cases there rather than scattering them across feature test files);
this file only covers the orchestration mechanism itself.
"""

import dataclasses

import pytest

from app.models.answer import STATUS_ANSWERED, STATUS_NEEDS_REVIEW
from app.models.chunk import Chunk
from app.models.document import Document
from app.providers import get_embedding_provider
from app.providers.base import LLMProvider
from app.rag.pipeline import LLMProviderError, PipelineResult, UnknownStepError, run_pipeline
from app.rag.steps import STEPS, CitationDraft, PipelineState, register_step


def _reverse_order(state: PipelineState, config: dict) -> PipelineState:
    """Test-double step: reverses the chunk list."""
    return dataclasses.replace(state, chunks=list(reversed(state.chunks)))


def _keep_first(state: PipelineState, config: dict) -> PipelineState:
    """Test-double step: keeps only the first chunk."""
    return dataclasses.replace(state, chunks=state.chunks[:1])


@pytest.fixture(autouse=True)
def _register_test_steps():
    """Register this file's test-double steps for the duration of each test.

    Snapshot/restore (rather than a one-time module-level `@register_step`)
    so `_test_reverse_order` / `_test_keep_first` never permanently leak into
    the shared, module-global `STEPS` registry for the rest of the test
    session -- that would break any later test/module asserting STEPS's exact
    key set (plausible once #10/#11 land the real catalog). This also means
    the duplicate-registration test below can't leak its extra registration
    attempt either.
    """
    snapshot = dict(STEPS)
    register_step("_test_reverse_order")(_reverse_order)
    register_step("_test_keep_first")(_keep_first)
    try:
        yield
    finally:
        STEPS.clear()
        STEPS.update(snapshot)


class _StubLLMProvider(LLMProvider):
    """Returns a fixed answer; used where a test only cares about chunks/order."""

    def generate(self, prompt: str, **opts: object) -> str:
        return "stub answer"


class _BoomLLMProvider(LLMProvider):
    """An LLM provider that always fails, for exercising error handling."""

    def generate(self, prompt: str, **opts: object) -> str:
        raise RuntimeError("llm unavailable")


def _seed_two_ordered_chunks(db_session, *, tenant_id: int, query: str) -> list[Chunk]:
    """Persist two chunks where the first is the nearer match to ``query``.

    Mirrors test_retrieve.py's near/far-vector trick so retrieve() returns
    them in a pinned, deterministic order: [near_chunk, far_chunk].
    """
    provider = get_embedding_provider()
    near_vector = provider.embed_query(query)
    # Pushes every dimension to the opposite end of [0, 1) (the mock's output
    # range), maximizing cosine distance from near_vector -- see
    # test_retrieve.py's identical trick for the same reasoning.
    far_vector = [1.0 - x for x in near_vector]
    document = Document(tenant_id=tenant_id, title="Ordering fixture")
    document.chunks = [
        Chunk(tenant_id=tenant_id, content="near chunk", embedding=near_vector),
        Chunk(tenant_id=tenant_id, content="far chunk", embedding=far_vector),
    ]
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document.chunks  # [near_chunk, far_chunk]


def test_run_pipeline_executes_steps_in_config_order(db_session, make_tenant) -> None:
    tenant = make_tenant()
    query = "ordering probe"
    near_chunk, far_chunk = _seed_two_ordered_chunks(db_session, tenant_id=tenant.id, query=query)

    # Order A: reverse [near, far] -> [far, near], THEN keep only the first
    # entry -> keeps the far chunk.
    result_a = run_pipeline(
        db_session,
        tenant_id=tenant.id,
        query=query,
        config={"pipeline": ["_test_reverse_order", "_test_keep_first"]},
        llm_provider=_StubLLMProvider(),
    )
    assert [c.id for c in result_a.chunks] == [far_chunk.id]

    # Order B: keep only the first entry of [near, far] (the near chunk),
    # THEN reverse a single-element list (no-op) -> keeps the near chunk.
    # Same two steps, opposite order, opposite outcome -- proves execution
    # order (not just "both ran") follows config["pipeline"].
    result_b = run_pipeline(
        db_session,
        tenant_id=tenant.id,
        query=query,
        config={"pipeline": ["_test_keep_first", "_test_reverse_order"]},
        llm_provider=_StubLLMProvider(),
    )
    assert [c.id for c in result_b.chunks] == [near_chunk.id]


def test_run_pipeline_raises_for_unregistered_step_name(db_session, make_tenant) -> None:
    tenant = make_tenant()
    assert "cite" not in STEPS  # #10 has not landed in this worktree

    with pytest.raises(UnknownStepError, match="cite"):
        run_pipeline(
            db_session,
            tenant_id=tenant.id,
            query="anything",
            config={"pipeline": ["cite"]},
            llm_provider=_StubLLMProvider(),
        )


def test_run_pipeline_skips_literal_retrieve_entry_in_pipeline_list(
    db_session, make_tenant
) -> None:
    # multi-tenant-design.md §3's sample config lists "retrieve" as a pipeline
    # entry; run_pipeline must treat it as a documented no-op, not raise
    # UnknownStepError (see app/rag/pipeline.py's module docstring).
    tenant = make_tenant()

    result = run_pipeline(
        db_session,
        tenant_id=tenant.id,
        query="anything",
        config={"pipeline": ["retrieve"]},
        llm_provider=_StubLLMProvider(),
    )

    assert isinstance(result, PipelineResult)
    assert result.answer == "stub answer"
    # Default PipelineState fields survive untouched when no step ran.
    assert result.status == STATUS_ANSWERED
    assert result.warnings == []
    assert result.citations == []


def test_run_pipeline_wraps_llm_provider_failure(db_session, make_tenant) -> None:
    tenant = make_tenant()

    with pytest.raises(LLMProviderError):
        run_pipeline(
            db_session,
            tenant_id=tenant.id,
            query="anything",
            config={"pipeline": []},
            llm_provider=_BoomLLMProvider(),
        )


def test_run_pipeline_builds_prompt_from_config_and_calls_provider(db_session, make_tenant) -> None:
    tenant = make_tenant()
    captured_prompts: list[str] = []

    class _CapturingLLMProvider(LLMProvider):
        def generate(self, prompt: str, **opts: object) -> str:
            captured_prompts.append(prompt)
            return "ok"

    result = run_pipeline(
        db_session,
        tenant_id=tenant.id,
        query="what are your hours",
        config={"answer": {"citation": "required"}, "pipeline": []},
        llm_provider=_CapturingLLMProvider(),
    )

    assert result.answer == "ok"
    assert len(captured_prompts) == 1
    # answer.citation=required must be reflected into the prompt text (prompt.py).
    assert "must be grounded in the context" in captured_prompts[0]
    assert "what are your hours" in captured_prompts[0]


def test_step_can_set_status_and_citation_with_empty_chunks(db_session, make_tenant) -> None:
    """The scenario Finding #1 flagged as impossible under the old (chunks-only)
    contract: a ground_check-like step must be able to set
    status=needs_review and attach a warning/citation draft even when there
    are zero grounding chunks -- there is no chunk to attach that to, so
    PipelineState (not Chunk) has to carry it.
    """
    tenant = make_tenant()  # no documents/chunks seeded -> retrieve() returns []

    def _flag_needs_review(state: PipelineState, config: dict) -> PipelineState:
        assert state.chunks == []  # the exact "no grounding chunks" case under test
        return dataclasses.replace(
            state,
            status=STATUS_NEEDS_REVIEW,
            warnings=[*state.warnings, "no grounding chunks found"],
            citations=[
                *state.citations,
                CitationDraft(snippet="unable to ground this answer", source_uri=None),
            ],
        )

    STEPS["_test_flag_needs_review"] = _flag_needs_review
    try:
        result = run_pipeline(
            db_session,
            tenant_id=tenant.id,
            query="a question with no matching documents",
            config={"pipeline": ["_test_flag_needs_review"]},
            llm_provider=_StubLLMProvider(),
        )
    finally:
        STEPS.pop("_test_flag_needs_review", None)

    assert result.chunks == []
    assert result.status == STATUS_NEEDS_REVIEW
    assert result.warnings == ["no grounding chunks found"]
    assert len(result.citations) == 1
    assert result.citations[0].snippet == "unable to ground this answer"


def test_register_step_raises_on_duplicate_name() -> None:
    # The autouse fixture above already registered "_test_reverse_order" for
    # this test; registering the same name again must fail loudly rather than
    # silently letting the second registration win (register_step's
    # documented behavior, previously never actually asserted).
    with pytest.raises(ValueError, match="_test_reverse_order"):
        register_step("_test_reverse_order")(_reverse_order)
