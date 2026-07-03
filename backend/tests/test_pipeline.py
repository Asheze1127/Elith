"""Tests for app.rag.pipeline.run_pipeline (#9): orchestration mechanism only.

Covers the DoD for #9: steps named in config["pipeline"] run in the exact
order given (an order-sensitive assertion, not just "both ran"), an
unregistered step name raises a clear, typed exception naming it, a literal
"retrieve" entry in config["pipeline"] (multi-tenant-design.md §3's sample
config) is a documented no-op rather than an error, and an LLM provider
failure is wrapped the same way ingestion/retrieve wrap provider failures.

Test-double steps are registered here, in this file only -- product code must
not contain placeholder cite/ground_check/stale_warning/contradiction_check
implementations (see the issue's scope notes). These step names are
deliberately test-only (`_test_*`) and never collide with a real catalog name.

Cross-tenant isolation of run_pipeline's retrieve() call has its own case in
test_tenant_scope.py (that file's docstring asks later issues to add their
isolation cases there rather than scattering them across feature test files);
this file only covers the orchestration mechanism itself.
"""

import pytest

from app.models.chunk import Chunk
from app.models.document import Document
from app.providers import get_embedding_provider
from app.providers.base import LLMProvider
from app.rag.pipeline import LLMProviderError, PipelineResult, UnknownStepError, run_pipeline
from app.rag.steps import STEPS, register_step


@register_step("_test_reverse_order")
def _reverse_order(chunks: list[Chunk], config: dict) -> list[Chunk]:
    """Test-double step: reverses the chunk list."""
    return list(reversed(chunks))


@register_step("_test_keep_first")
def _keep_first(chunks: list[Chunk], config: dict) -> list[Chunk]:
    """Test-double step: keeps only the first chunk."""
    return chunks[:1]


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
