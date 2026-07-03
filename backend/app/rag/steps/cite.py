"""``cite`` step (#10): attach citation drafts and source metadata to chunks.

Registers under ``"cite"`` (process-flow.md §2.1's documented pipeline order:
``retrieve -> stale_warning -> contradiction_check -> ground_check -> cite ->
generate``, i.e. cite commonly runs last among the named steps, immediately
before prompt-building/generation). ``config["pipeline"]`` is data, though, so
this step must not assume any particular position, nor that any other step
ran before it -- it only reads ``state.chunks``/``state.citations`` and
appends to them.

What this step does
--------------------
For every chunk in ``state.chunks``, builds one ``CitationDraft`` carrying:
- ``chunk_id`` / ``document_id``: identify what was cited.
- ``snippet``: a bounded excerpt of ``chunk.content`` (see
  ``_SNIPPET_MAX_CHARS`` below) -- not the full chunk body, which can be
  several paragraphs long.
- ``source_uri`` / ``source_updated_at``: the "資料メタ" (source material
  metadata) pulled from the chunk's document (multi-tenant-design.md §3's
  ``answer.show_source_metadata`` names this data). This step always
  populates it; deciding whether/how to surface it to the end user (that
  flag's actual effect) is #12's job when it assembles the final ``/chat``
  response envelope -- out of scope here (see the issue's "what NOT to
  build").

Accessing ``chunk.document`` triggers a lazy SQLAlchemy load per chunk (the
query in ``app.rag.retrieve.retrieve`` does not eager-load it) -- an accepted
N+1 tradeoff at this data scale (see the issue notes); ``retrieve.py`` is
already reviewed/merged and is out of this issue's scope to change.

Design decision: what "根拠なしの断定を抑止" can mean here
------------------------------------------------------------
process-flow.md §2.1 states cite's contract as: "``citation: required`` なら
根拠なしの断定を抑止し、資料メタを添付" (when citation is required, suppress
unfounded assertions, and attach source metadata). Structurally, this step
runs entirely inside the pre-generation phase (``retrieve -> ... -> steps ->
build_prompt -> generate``, see ``app/rag/pipeline.py``) -- the LLM has not
produced any answer text by the time this step runs, so "suppressing an
assertion" cannot mean editing or vetoing generated text; no such text exists
yet for this step to act on.

The prompt layer (#9's ``app.rag.prompt.build_prompt``) already instructs the
model not to guess when ``answer.citation == "required"`` (its "Every factual
claim must be grounded..." branch). That is the first line of defense, but it
is a natural-language instruction the model is not guaranteed to follow. This
step's buildable contribution is a second, pipeline-level line of defense:
when citation is required and there is nothing to cite (``state.chunks`` is
empty), this step sets ``state.status = STATUS_NO_DATA`` so that whatever
eventually assembles the ``/chat`` response (#12) has a structural signal --
independent of what the LLM actually generated -- that this answer has zero
grounding under a policy that requires it, and must not be presented as a
confident, cited answer.

``STATUS_NO_DATA`` (not ``STATUS_NEEDS_REVIEW``) is the right choice here per
``app.models.answer``'s docstring and the distinction process-flow.md draws
between its §5.1 "根拠不足" (weak-but-present grounding -- ``ground_check``'s
territory, #11) and its §5.2 "データなし（検索ヒット0）" (zero search hits).
Zero chunks by the time ``cite`` runs is exactly the latter case -- there is
no partial/weak grounding to review, there is none at all.

Because ``config["pipeline"]`` is data and this step is not guaranteed to run
last (or first, or at all alongside any particular other step), it must not
clobber a status a different step already changed away from the untouched
default ``STATUS_ANSWERED`` -- doing so could silently overturn e.g.
``ground_check``'s own determination about the same answer. This step uses
``app.rag.steps.escalate_status``, the same tighten-only helper ``ground_check``
(#11) uses, so the two steps agree on one ordering regardless of which runs
first (both independently arrived at a "never loosen" rule in review, with
two different mechanisms; they were unified into one shared helper).

Zero chunks with citation NOT required is not an error either
(process-flow.md §5.2: "no data found" is a normal, user-facing outcome) --
this step simply contributes no citations in that case and does not touch
``status``.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from app.models.answer import STATUS_NO_DATA
from app.rag.steps import CitationDraft, PipelineState, escalate_status, register_step

# A citation snippet is a short preview, not the full passage -- chunks can be
# several paragraphs long, and re-inlining the whole body next to the answer
# defeats the point of a "citation" as a pointer back to the source. 200
# characters is enough for a reader to recognize which passage was cited
# without duplicating it wholesale.
_SNIPPET_MAX_CHARS = 200


def _build_snippet(content: str) -> str:
    """Return a bounded excerpt of ``content`` for a citation preview."""
    if len(content) <= _SNIPPET_MAX_CHARS:
        return content
    return content[:_SNIPPET_MAX_CHARS].rstrip() + "..."


@register_step("cite")
def cite(state: PipelineState, config: dict[str, Any]) -> PipelineState:
    """Append one ``CitationDraft`` per chunk; flag no-data under required citation.

    See the module docstring for the full status-escalation rationale. Zero
    chunks is handled explicitly and gracefully (not an exception) either
    way -- it is a normal, expected pipeline state (process-flow.md §5.2).
    """
    answer_cfg = config.get("answer")
    # config is unvalidated tenant JSONB (mirrors app.rag.prompt's defensive
    # shape handling) -- a mis-seeded "answer" that isn't a dict is treated as
    # "citation not required" rather than raising.
    citation_required = isinstance(answer_cfg, dict) and answer_cfg.get("citation") == "required"

    new_drafts = [
        CitationDraft(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            snippet=_build_snippet(chunk.content),
            source_uri=chunk.document.source_uri,
            source_updated_at=chunk.document.source_updated_at,
        )
        for chunk in state.chunks
    ]

    # Second line of defense (see module docstring): nothing to cite under a
    # required-citation policy -- propose STATUS_NO_DATA, but escalate_status
    # only actually applies it if that's more severe than whatever status is
    # already there (e.g. leaves an earlier step's own worse verdict alone).
    candidate_status = STATUS_NO_DATA if (citation_required and not state.chunks) else state.status

    return dataclasses.replace(
        state,
        status=escalate_status(state.status, candidate_status),
        citations=[*state.citations, *new_drafts],
    )
