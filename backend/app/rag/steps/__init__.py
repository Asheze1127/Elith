"""Named pipeline-step registry: the common, shared step catalog (#9).

directory.md §3 places the pipeline's named parts here (``app/rag/steps/``),
one module per step (``stale_warning.py`` / ``contradiction_check.py`` /
``ground_check.py`` / ``cite.py``). None of those exist yet -- #10, #11, #18,
#19 each add exactly one of them and register it with ``@register_step(...)``
below. This module defines only the mechanism (the registry + decorator) that
those future modules will conform to; it intentionally contains no step logic
of its own (see the issue's "what NOT to build" list).

Step contract
-------------
A step is any callable matching ``StepFn``::

    def my_step(chunks: list[Chunk], config: dict[str, Any]) -> list[Chunk]:
        ...

- ``chunks``: the chunks produced so far -- either straight from
  ``app.rag.retrieve.retrieve()`` (if this is the first step) or whatever the
  previous step in ``config["pipeline"]`` returned.
- ``config``: the full tenant_config JSONB dict (multi-tenant-design.md §3),
  e.g. a step reads ``config["warnings"]["stale_sources"]`` for its own
  on/off flag. A step must treat this as read-only.
- returns: the chunks to hand to the next step (or, for the last step, to
  ``app.rag.prompt.build_prompt``). A step should return a new list rather
  than mutating its input in place, so the orchestrator's running variable in
  ``app.rag.pipeline.run_pipeline`` remains the single source of truth for
  "what has happened so far."
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

from collections.abc import Callable
from typing import Any

from app.models.chunk import Chunk

# A pipeline step: takes the chunks produced so far plus the full tenant
# config, returns the chunks to pass on. See the module docstring for the
# full contract (read-only config, no in-place mutation, own exception types).
StepFn = Callable[[list[Chunk], dict[str, Any]], list[Chunk]]

# The shared step catalog. Keys are the names tenant_config.pipeline entries
# name (multi-tenant-design.md §3); populated by each step module's
# `@register_step(...)` at import time, not by this module directly.
STEPS: dict[str, StepFn] = {}


def register_step(name: str) -> Callable[[StepFn], StepFn]:
    """Decorator that registers a step function under ``name`` in ``STEPS``.

    Usage (in a future step module, e.g. app/rag/steps/cite.py)::

        @register_step("cite")
        def cite(chunks: list[Chunk], config: dict[str, Any]) -> list[Chunk]:
            ...

    Raises ``ValueError`` if ``name`` is already registered.
    """

    def _decorator(fn: StepFn) -> StepFn:
        if name in STEPS:
            raise ValueError(f"step {name!r} is already registered")
        STEPS[name] = fn
        return fn

    return _decorator
