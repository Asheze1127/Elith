"""Common RAG pipeline orchestrator (#9): retrieve -> named steps -> prompt -> generate.

Runs the identical code path for every tenant; only ``config`` (a tenant's
tenant_config JSONB dict) and ``tenant_id``/``workspace_id`` differ per call
(multi-tenant-design.md §5's ``run_pipeline`` pseudocode). This module owns
step lookup/dispatch and LLM invocation; it does not implement any named
step's logic (that's #10/#11/#18/#19, see ``app.rag.steps``) and it does not
build the prompt text itself (that's ``app.rag.prompt.build_prompt``).

Doc inconsistency note (flagged rather than silently resolved, per the issue):
multi-tenant-design.md §3's sample tenant_config lists
``"pipeline": ["retrieve", "stale_warning", "contradiction_check", "ground_check", "cite"]``
i.e. it includes ``"retrieve"`` as a pipeline entry. multi-tenant-design.md §5's
own pseudocode and process-flow.md §2/§2.1's diagram instead treat retrieve as
a distinct phase that runs *before* the named-step loop, never one of
``STEPS``. We follow the latter (process-flow.md is the more detailed,
authoritative source on execution order): ``retrieve`` is not registered in
``app.rag.steps.STEPS``. Since a config copy-pasted from the §3 sample is a
real, foreseeable input, a literal ``"retrieve"`` entry in
``config["pipeline"]`` is treated as a no-op and skipped rather than raising
``UnknownStepError`` -- see the loop below.

Step contract, in brief (full detail in ``app.rag.steps``'s module docstring):
each step receives and returns a whole ``PipelineState`` (chunks + status +
warnings + citation drafts), not a bare chunk list -- this lets a step like
``ground_check`` set ``status`` even with zero chunks, which a chunk-only
contract could not express.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.answer import STATUS_ANSWERED, STATUS_NO_DATA
from app.models.chunk import Chunk
from app.providers import get_llm_provider
from app.providers.base import EmbeddingProvider, LLMProvider
from app.rag.prompt import build_prompt
from app.rag.retrieve import DEFAULT_TOP_K, retrieve
from app.rag.steps import STEPS, CitationDraft, PipelineState, WarningDraft

# Pipeline entries naming this are a no-op (see module docstring): retrieve is
# a distinct prior phase, not a registry-dispatched step.
_RETRIEVE_STEP_NAME = "retrieve"
NO_DATA_ANSWER = "該当資料が見つかりませんでした。担当部署または管理者に確認してください。"


class PipelineError(Exception):
    """Base class for recoverable pipeline failures with a user-facing message."""


class UnknownStepError(PipelineError):
    """Raised when ``config["pipeline"]`` names a step absent from the registry.

    This is a real, expected scenario during this feature's staged rollout
    (e.g. a tenant_config already lists "cite" before #10 lands the actual
    step), so the message names the offending step -- an operator (or test)
    reading it should not need a stack trace to know what to fix.
    """


class LLMProviderError(PipelineError):
    """Raised when the LLM provider fails to generate an answer.

    Wraps the underlying provider/SDK exception (mirrors
    ``ingestion.pipeline.EmbeddingProviderError`` /
    ``app.rag.retrieve.EmbeddingProviderError``) so callers can show a clear
    message without leaking a raw stack trace or SDK internals
    (process-flow.md §5.3).
    """


@dataclass
class PipelineResult:
    """Outcome of one ``run_pipeline()`` call.

    Carries everything the final ``PipelineState`` accumulated: the chunk
    list after every configured step ran, the generated answer text, and the
    answer-level ``status``/``warnings``/``citations`` any step attached.
    Those three don't map onto a single chunk (see ``PipelineState``'s
    docstring), so they must survive out of ``run_pipeline`` as their own
    fields rather than being dropped. This is still not the ``/chat``
    response envelope -- deciding its HTTP shape/wording from these fields is
    #12's job -- it is the raw material #12 will need.
    """

    chunks: list[Chunk]
    answer: str
    status: str = STATUS_ANSWERED
    warnings: list[WarningDraft] = field(default_factory=list)
    citations: list[CitationDraft] = field(default_factory=list)


def run_pipeline(
    db: Session,
    *,
    tenant_id: int,
    query: str,
    config: dict[str, Any],
    workspace_id: int | None = None,
    top_k: int = DEFAULT_TOP_K,
    mode: str | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    llm_provider: LLMProvider | None = None,
) -> PipelineResult:
    """Run retrieve, then ``config["pipeline"]``'s named steps in order, then generate.

    ``tenant_id`` / ``workspace_id`` are forwarded to ``retrieve()`` unchanged
    -- this function must never open any other, unscoped path to chunk data
    (permission-design.md §3). ``embedding_provider`` / ``llm_provider`` are
    optional injection points for callers/tests (mirrors ``retrieve()``'s own
    ``embedding_provider`` parameter); when omitted, both default to
    ``get_llm_provider()`` / the embedding provider ``retrieve()`` picks via
    environment config -- never a concrete SDK import here.

    Note: ``config["search"]["scope"]`` (multi-tenant-design.md §3) is NOT
    translated into ``workspace_id`` here -- deciding which workspace(s) a
    scope value like "all" or a department name maps to is the caller's job
    (#12), not this orchestrator's; ``workspace_id`` must already be resolved
    by the time it is passed in.

    Raises ``UnknownStepError`` if a name in ``config["pipeline"]`` is not
    registered, ``LLMProviderError`` if answer generation fails, or whatever
    ``retrieve()`` itself raises (``EmbeddingProviderError`` / ``ValueError``)
    unchanged.
    """
    chunks = retrieve(
        db,
        tenant_id=tenant_id,
        query=query,
        workspace_id=workspace_id,
        top_k=top_k,
        embedding_provider=embedding_provider,
    )
    effective_config = _with_requested_mode(config, mode)
    state = PipelineState(chunks=chunks)

    for step_name in effective_config.get("pipeline", []):
        if step_name == _RETRIEVE_STEP_NAME:
            continue
        try:
            step_fn = STEPS[step_name]
        except KeyError:
            raise UnknownStepError(f"unknown pipeline step: {step_name!r}") from None
        state = step_fn(state, effective_config)

    if state.status == STATUS_NO_DATA:
        return PipelineResult(
            chunks=state.chunks,
            answer=NO_DATA_ANSWER,
            status=state.status,
            warnings=state.warnings,
            citations=state.citations,
        )

    prompt = build_prompt(effective_config, state.chunks, query)

    provider = llm_provider or get_llm_provider()
    try:
        answer = provider.generate(prompt)
    except Exception as exc:  # provider/SDK errors vary; normalize to one type
        raise LLMProviderError(f"failed to generate answer: {exc}") from exc

    return PipelineResult(
        chunks=state.chunks,
        answer=answer,
        status=state.status,
        warnings=state.warnings,
        citations=state.citations,
    )


def _with_requested_mode(config: dict[str, Any], mode: str | None) -> dict[str, Any]:
    """Return a shallow config copy whose answer.default_mode is ``mode``."""
    if mode is None:
        return config

    answer_value = config.get("answer")
    answer = answer_value if isinstance(answer_value, dict) else {}
    return {**config, "answer": {**answer, "default_mode": mode}}
