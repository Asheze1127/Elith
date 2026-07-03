"""``ground_check`` step (#11): flag weakly-grounded answers for review.

process-flow.md §2.1: "ground_check：回答が引用に基づくか簡易確認。弱ければ
`status = needs_review`。" This step runs before ``generate()`` -- looking at
``app.rag.pipeline.run_pipeline``, the named steps all run, THEN the prompt is
built and the LLM is called -- so there is no generated answer text yet at
step time. "Is the answer grounded in citations" therefore cannot be checked
by inspecting text; the only signal available is what is already sitting in
``state`` when this step runs: ``state.chunks`` (always present) and, if a
tenant's ``config["pipeline"]`` happened to run #10's ``cite`` step first,
``state.citations`` (not assumed -- a config could list ``ground_check``
before ``cite``, or omit ``cite`` entirely). ``app.rag.retrieve.retrieve()``
does not thread a distance/similarity score through at all (see that module's
docstring), so the only proxy this "簡易" (simple) check can use is chunk
COUNT as a stand-in for "how much material backs this answer."

Design decision: two distinct "weak" outcomes, not one
-------------------------------------------------------
process-flow.md draws a line between two outcomes that are easy to conflate:

- §5.1 "根拠不足" (insufficient grounding): SOME chunks exist, but too thin to
  answer with confidence -> don't assert, ``status = STATUS_NEEDS_REVIEW``,
  "確認が必要".
- §5.2 "データなし" (no data): ZERO search hits -> "該当資料が見つからない" +
  an escalation/contact path -- a stronger, distinct outcome from §5.1's
  "some material, but weak" case.

This step maps those onto ``app.models.answer``'s constants -- but only the
zero-chunk case is hardcoded to ``STATUS_NO_DATA`` (exactly the §5.2 case --
there is nothing at all to ground an answer in, and no tenant_config field
names this outcome). The "some but too few" (§5.1) case is data, not code:
``multi-tenant-design.md`` §3's sample tenant_config literally has an
``answer.low_confidence_action`` field ("根拠が弱い→断定せず「確認が必要」"),
so ``0 < chunk_count < MIN_GROUNDING_CHUNKS`` uses whatever status string the
tenant configured there (defaulting to ``STATUS_NEEDS_REVIEW`` if the field
or the whole ``answer`` section is missing/malformed -- config is unvalidated
JSONB, mirroring ``app.rag.prompt``'s defensive shape handling).

Threshold reasoning (``MIN_GROUNDING_CHUNKS``)
-----------------------------------------------
A single retrieved chunk is one document's perspective with no corroboration
-- there is no way for a check this simple (no LLM call, no distance score) to
tell whether that lone chunk is representative, taken out of context, or
merely the least-bad match ``retrieve()`` could find. Requiring at least 2
chunks gives one independent point of corroboration before this step calls
the grounding "enough" to leave ``status`` alone. 2 is deliberately the
smallest number above 1 that expresses "not just one lonely match" -- a
higher bar (e.g. 3+) would start flagging genuinely thin-content tenants (a
short internal FAQ where most questions legitimately have 1-2 relevant
chunks) as ``needs_review`` by default, trading too many false positives for
a marginally stricter check.

Never loosen an already-worse status
-------------------------------------
A step earlier in ``config["pipeline"]`` may have already set ``state.status``
to something worse than what this step would independently conclude --
pipeline order is tenant_config data, not fixed (multi-tenant-design.md §3),
so ``ground_check`` cannot assume it runs first or last. This step must never
overwrite a worse status with a better one just because its own, narrower
chunk-count signal looks fine in isolation -- it may only *tighten* (move
``status`` toward worse), never loosen. ``_STATUS_SEVERITY`` ranks the three
known constants from best to worst; a status this step doesn't recognize (the
status vocabulary is tenant-config data, not a DB enum -- see
``app.models.answer``'s module docstring) is treated as already maximally
severe, so this step never "improves" a status it doesn't understand either.

Exceptions
----------
This step performs no I/O and reads only fields ``PipelineState`` already
guarantees the shape of (``chunks``: a list, ``status``: a str) -- there is no
external call, parse, or piece of user input here that can fail in a
user-relevant way. Unlike ``retrieve``/``pipeline`` (which wrap provider
failures into their own exception types), this module deliberately defines
none: there is nothing to wrap, so it is total over any valid
``PipelineState``.
"""

from __future__ import annotations

import dataclasses

from app.models.answer import STATUS_ANSWERED, STATUS_NEEDS_REVIEW, STATUS_NO_DATA
from app.rag.steps import PipelineState, register_step

# See "Threshold reasoning" above: 2 is the smallest number that expresses
# "more than one lonely, uncorroborated match".
MIN_GROUNDING_CHUNKS = 2

# Best -> worst. Used to enforce "tighten only, never loosen": this step must
# not replace a worse status a prior step already set with a better one.
_STATUS_SEVERITY = {
    STATUS_ANSWERED: 0,
    STATUS_NEEDS_REVIEW: 1,
    STATUS_NO_DATA: 2,
}

# An unrecognized status is presumed at least as severe as the worst known
# one, so this step never "improves" a status it doesn't understand.
_UNKNOWN_STATUS_SEVERITY = _STATUS_SEVERITY[STATUS_NO_DATA]


@register_step("ground_check")
def ground_check(state: PipelineState, config: dict) -> PipelineState:
    """Set ``state.status`` from a chunk-count proxy for grounding strength.

    Only ever adjusts ``state.status``; never touches ``state.chunks`` or
    ``state.citations`` -- filtering/reordering chunks is out of scope for
    this step (see the issue's DoD). See the module docstring for the
    zero-vs-few-chunks status mapping and the "never loosen" rule.
    """
    answer_cfg = config.get("answer")
    # multi-tenant-design.md §3's sample tenant_config literally names the
    # weak-grounding status as data: `answer.low_confidence_action`. This is
    # the customer difference this step must read, not hardcode (the
    # "differences are data, not code" principle) -- a tenant could set this
    # to something other than "needs_review". config is unvalidated JSONB
    # (mirrors app.rag.prompt's defensive shape handling), so a missing/
    # malformed "answer" section falls back to the same default this step
    # used before this field was wired in.
    low_confidence_status = (
        answer_cfg.get("low_confidence_action", STATUS_NEEDS_REVIEW)
        if isinstance(answer_cfg, dict)
        else STATUS_NEEDS_REVIEW
    )

    chunk_count = len(state.chunks)
    if chunk_count == 0:
        # process-flow.md §5.2: zero hits at all -> "no data", not merely
        # "weak". Not config-driven: there is no tenant_config field for
        # this outcome, unlike the weak-grounding case below.
        candidate_status = STATUS_NO_DATA
    elif chunk_count < MIN_GROUNDING_CHUNKS:
        # process-flow.md §5.1: some material, but too thin to trust --
        # what to do about it is the tenant's own configured action.
        candidate_status = low_confidence_status
    else:
        # Enough chunks: this step has no signal to make the outcome worse.
        candidate_status = STATUS_ANSWERED

    current_severity = _STATUS_SEVERITY.get(state.status, _UNKNOWN_STATUS_SEVERITY)
    # candidate_status may be a value this module doesn't recognize (a tenant
    # can set low_confidence_action to any string); treat an unrecognized
    # candidate as at least STATUS_NEEDS_REVIEW's severity rather than
    # silently skipping it as "no signal" -- the tenant explicitly configured
    # it to fire on weak grounding, so it must never be a no-op.
    candidate_severity = _STATUS_SEVERITY.get(
        candidate_status, _STATUS_SEVERITY[STATUS_NEEDS_REVIEW]
    )
    if candidate_severity <= current_severity:
        # Tighten-only: never loosen a status a prior step already set worse
        # (including a no-op where the candidate matches the current status).
        return state

    return dataclasses.replace(state, status=candidate_status)
