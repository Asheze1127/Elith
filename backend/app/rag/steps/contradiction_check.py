"""``contradiction_check`` step (#19): warn on likely conflicting chunks."""

from __future__ import annotations

import dataclasses
from typing import Any, Literal

from app.rag.steps import PipelineState, WarningDraft, register_step

Polarity = Literal["positive", "negative"]

_POSITIVE_PATTERNS = (
    "できます",
    "可能",
    "許可",
    "あります",
    "can ",
    "allowed",
    "yes",
)
_NEGATIVE_PATTERNS = (
    "できません",
    "不可",
    "禁止",
    "不可能",
    "ありません",
    "cannot",
    "can't",
    "not allowed",
    "prohibited",
    "no ",
)


def _warnings_enabled(config: dict[str, Any]) -> bool:
    warnings_cfg = config.get("warnings")
    return isinstance(warnings_cfg, dict) and warnings_cfg.get("contradiction") is True


def _polarity(content: str) -> Polarity | None:
    normalized = f" {content.lower()} "
    if any(pattern in normalized for pattern in _NEGATIVE_PATTERNS):
        return "negative"
    if any(pattern in normalized for pattern in _POSITIVE_PATTERNS):
        return "positive"
    return None


@register_step("contradiction_check")
def contradiction_check(state: PipelineState, config: dict[str, Any]) -> PipelineState:
    """Append a typed warning when simple positive/negative signals conflict."""
    if not _warnings_enabled(config) or len(state.chunks) < 2:
        return state

    polarities = {_polarity(chunk.content) for chunk in state.chunks}
    if {"positive", "negative"}.issubset(polarities):
        return dataclasses.replace(
            state,
            warnings=[
                *state.warnings,
                WarningDraft(
                    type="contradiction",
                    message=(
                        "参照資料間で回答方針が矛盾している可能性があります。"
                        "担当部署で確認してください。"
                    ),
                ),
            ],
        )
    return state
