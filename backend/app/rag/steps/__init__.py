"""Named pipeline-step registry: the common, shared step catalog (#9).

directory.md §3 places the pipeline's named parts here (``app/rag/steps/``),
one module per step (``stale_warning.py`` / ``contradiction_check.py`` /
``ground_check.py`` / ``cite.py``). None of those exist yet -- #10, #11, #18,
#19 each add exactly one of them and register it with ``@register_step(...)``
below. This module defines only the mechanism (the registry + decorator +
the state object threaded through steps) that those future modules will
conform to; it intentionally contains no step logic of its own (see the
issue's "what NOT to build" list).

Step contract
-------------
A step is any callable matching ``StepFn``::

    def my_step(state: PipelineState, config: dict[str, Any]) -> PipelineState:
        ...

- ``state``: a ``PipelineState`` carrying everything produced so far -- the
  chunks (either straight from ``app.rag.retrieve.retrieve()``, if this is
  the first step, or whatever the previous step returned), plus the
  answer-level ``status``/``warnings``/``citations`` accumulated by any
  earlier step. (This widened from a bare ``list[Chunk]`` after review of the
  first version of this contract -- see ``PipelineState``'s docstring for
  why chunks alone can't carry what #10/#11 need.)
- ``config``: the full tenant_config JSONB dict (multi-tenant-design.md §3),
  e.g. a step reads ``config["warnings"]["stale_sources"]`` for its own
  on/off flag. A step must treat this as read-only.
- returns: a ``PipelineState`` to hand to the next step (or, for the last
  step, to ``app.rag.pipeline.run_pipeline``'s prompt-building/generate
  phase). A step must return a NEW ``PipelineState`` (e.g. via
  ``dataclasses.replace``) rather than mutating its input in place, so the
  orchestrator's running variable in ``run_pipeline`` remains the single
  source of truth for "what has happened so far." This applies to every
  field, not just ``chunks`` -- e.g. append to a *copy* of
  ``state.warnings``, don't call ``state.warnings.append(...)``.
- may raise: any exception. This package deliberately does not impose a
  shared step-level exception type -- #10/#11/#18/#19's steps may have very
  different failure modes -- but a step that can fail in a user-relevant way
  should define its own exception mirroring the existing style
  (``app.rag.retrieve.RetrieveError`` / ``ingestion.pipeline.IngestionError``).
  Whatever a step raises propagates unwrapped through ``run_pipeline``.

Registration mechanism
-----------------------
``register_step(name)`` is a decorator; it registers the decorated callable
into the module-level ``STEPS`` dict under ``name`` and raises ``ValueError``
if that name is already registered. A duplicate name is treated as a bug (two
modules claiming the same pipeline step name), not a legitimate override, so
it fails loudly at import time instead of silently letting the later import
win.

Why this lives in ``app/rag/steps/`` and not ``app/policies/registry.py``:
directory.md §3 describes ``app/policies/registry.py`` as the registry for
*bespoke*, single-tenant strategies (e.g. C-company's medical-escalation
check, permission-design.md §6-3) -- logic only one customer's config ever
selects. This registry is the opposite: the shared, common-catalog steps that
*every* tenant's ``config["pipeline"]`` can name (multi-tenant-design.md §7,
"共通機能として戻すもの"). Keeping them apart mirrors that distinction; a
bespoke policy could later be wrapped and registered here too, once one
exists, but that call belongs to whoever adds the first bespoke policy.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models.answer import STATUS_ANSWERED, STATUS_NEEDS_REVIEW, STATUS_NO_DATA
from app.models.chunk import Chunk


@dataclass
class WarningDraft:
    """A typed warning produced by a pipeline step before API serialization."""

    type: str
    message: str


@dataclass
class CitationDraft:
    """A citation candidate produced by a step, before persistence (#12).

    Mirrors the fields of ``app.models.citation.Citation`` that matter before
    an ``answer_id`` exists -- that FK is only assigned once #12 persists the
    ``Answer`` row, so this is deliberately NOT the ORM model. A step (``cite``,
    most likely, #10) builds these in memory from whatever chunk/document it
    is citing; #12 later turns each draft into a real ``Citation`` row
    attached to the persisted ``Answer``.
    """

    chunk_id: int | None = None
    document_id: int | None = None
    snippet: str | None = None
    source_uri: str | None = None
    source_updated_at: datetime | None = None


@dataclass
class PipelineState:
    """State threaded through pipeline steps and back to ``run_pipeline``.

    The original version of this contract passed a bare ``list[Chunk]``
    between steps. Review of #10 (``cite``) and #11 (``ground_check``)'s
    actual needs showed that's insufficient:

    - ``ground_check`` must be able to set an answer-level ``status`` (see
      ``app.models.answer.STATUS_*``) even when ``chunks`` is EMPTY -- "no
      grounding chunks" / "weak grounding" is exactly the case that should
      produce ``STATUS_NEEDS_REVIEW``, and there is no chunk to attach that
      to in that scenario.
    - ``cite`` must produce citation data that isn't a ``Chunk`` field
      (``snippet``/``source_uri``/etc., see ``CitationDraft`` above).
    - ``stale_warning`` / ``contradiction_check`` (#18/#19) need to append
      warnings that also aren't chunk-scoped (e.g. "source X is stale" isn't
      a property of any single returned chunk once several were merged).

    Steps receive and return this whole object so those answer-level outputs
    have a defined home, without smuggling state onto ``Chunk`` (a persisted
    SQLAlchemy model -- attributes set on it in memory would not survive a
    ``refresh()``, and per-chunk state is the wrong shape for an answer-level
    fact anyway) and without ever making ``config`` mutable (it stays
    strictly read-only; steps only ever read from it).

    Convention: a step must return a NEW ``PipelineState`` (e.g. via
    ``dataclasses.replace(state, ...)``), never mutate ``state`` in place --
    including its list fields (``chunks``/``warnings``/``citations``): build
    a new list rather than calling ``.append()`` on the one you received.
    """

    chunks: list[Chunk]
    # "Nothing has gone wrong yet" starting point; a step may downgrade this
    # (e.g. to STATUS_NEEDS_REVIEW) but this module does not interpret the
    # value itself -- assembling the final /chat response from it is #12's job.
    status: str = STATUS_ANSWERED
    warnings: list[WarningDraft] = field(default_factory=list)
    citations: list[CitationDraft] = field(default_factory=list)


# A pipeline step: takes the running PipelineState plus the full tenant
# config, returns the (new) PipelineState to pass on. See the module
# docstring for the full contract (read-only config, no in-place mutation,
# own exception types).
StepFn = Callable[[PipelineState, dict[str, Any]], PipelineState]

# The shared step catalog. Keys are the names tenant_config.pipeline entries
# name (multi-tenant-design.md §3); populated by each step module's
# `@register_step(...)` at import time, not by this module directly.
STEPS: dict[str, StepFn] = {}


def register_step(name: str) -> Callable[[StepFn], StepFn]:
    """Decorator that registers a step function under ``name`` in ``STEPS``.

    Usage (in a future step module, e.g. app/rag/steps/cite.py)::

        @register_step("cite")
        def cite(state: PipelineState, config: dict[str, Any]) -> PipelineState:
            ...

    Raises ``ValueError`` if ``name`` is already registered.
    """

    def _decorator(fn: StepFn) -> StepFn:
        if name in STEPS:
            raise ValueError(f"step {name!r} is already registered")
        STEPS[name] = fn
        return fn

    return _decorator


# Best -> worst. Shared by every step that can set ``PipelineState.status``
# (currently ``cite`` and ``ground_check``; ``stale_warning``/
# ``contradiction_check`` #18/#19 will likely join them) so they all agree on
# one "tighten only, never loosen" ordering rather than each inventing its
# own comparison (the two original implementations independently converged on
# slightly different rules -- an equality-from-default check vs. a severity
# ranking -- which review found could, in principle, diverge by pipeline
# order once a third status-setting step existed; unifying here removes that
# risk for good).
_STATUS_SEVERITY = {
    STATUS_ANSWERED: 0,
    STATUS_NEEDS_REVIEW: 1,
    STATUS_NO_DATA: 2,
}


def escalate_status(current_status: str, candidate_status: str) -> str:
    """Return whichever of ``current_status``/``candidate_status`` is more severe.

    Never loosens: if ``candidate_status`` is not strictly more severe than
    ``current_status``, ``current_status`` is returned unchanged (including
    when they're equal). A status string this module doesn't recognize can
    appear on either side, since the status vocabulary is tenant-config data,
    not a DB enum (``app.models.answer``'s module docstring):

    - An unrecognized ``current_status`` is treated as maximally severe, so a
      step never "improves" a status set by something it doesn't understand
      (e.g. a future bespoke policy's own status string).
    - An unrecognized ``candidate_status`` (e.g. a tenant's own
      ``answer.low_confidence_action`` value that isn't one of the three
      built-in constants) is treated as at least ``STATUS_NEEDS_REVIEW``'s
      severity, never as "no signal" -- a step that explicitly proposes a
      status change must never be silently ignored just because this module
      doesn't recognize the string.
    """
    current_severity = _STATUS_SEVERITY.get(current_status, _STATUS_SEVERITY[STATUS_NO_DATA])
    candidate_severity = _STATUS_SEVERITY.get(
        candidate_status, _STATUS_SEVERITY[STATUS_NEEDS_REVIEW]
    )
    return candidate_status if candidate_severity > current_severity else current_status


def _register_builtin_steps() -> None:
    """Import built-in step modules so their decorators populate STEPS."""
    importlib.import_module("app.rag.steps.cite")
    importlib.import_module("app.rag.steps.contradiction_check")
    importlib.import_module("app.rag.steps.ground_check")
    importlib.import_module("app.rag.steps.stale_warning")


_register_builtin_steps()
