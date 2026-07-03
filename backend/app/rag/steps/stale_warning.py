"""``stale_warning`` step (#18): warn when retrieved source material is old."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from typing import Any

from app.models.document import Document
from app.rag.steps import PipelineState, WarningDraft, register_step

STALE_SOURCE_MAX_AGE_DAYS = 365


def _warnings_enabled(config: dict[str, Any]) -> bool:
    warnings_cfg = config.get("warnings")
    return isinstance(warnings_cfg, dict) and warnings_cfg.get("stale_sources") is True


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _source_timestamp(document: Document) -> datetime | None:
    return document.source_updated_at or document.updated_at


def _is_stale(document: Document, *, now: datetime) -> bool:
    timestamp = _source_timestamp(document)
    if timestamp is None:
        return True
    return now - _ensure_aware(timestamp) > timedelta(days=STALE_SOURCE_MAX_AGE_DAYS)


@register_step("stale_warning")
def stale_warning(state: PipelineState, config: dict[str, Any]) -> PipelineState:
    """Append one warning when any retrieved document is stale.

    The document model has no workflow ``status`` column yet, so this step uses
    ``source_updated_at`` and falls back to row ``updated_at`` as the available
    freshness metadata documented in app.models.document.
    """
    if not _warnings_enabled(config):
        return state

    now = datetime.now(UTC)
    seen_documents: set[int | str] = set()
    warnings = list(state.warnings)

    for chunk in state.chunks:
        document = chunk.document
        key: int | str = document.id if document.id is not None else document.title
        if key in seen_documents:
            continue
        seen_documents.add(key)
        if not _is_stale(document, now=now):
            continue

        warnings.append(
            WarningDraft(
                type="stale_sources",
                message=(
                    f"参照資料「{document.title}」は更新日が古い、または更新日を確認できません。"
                    "担当部署で最新版か確認してください。"
                ),
            )
        )

    return dataclasses.replace(state, warnings=warnings)
