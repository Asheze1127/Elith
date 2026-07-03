"""Tests for contradiction_check: conflicting source chunks produce a warning."""

from app.models.chunk import EMBEDDING_DIM, Chunk
from app.rag.steps import PipelineState
from app.rag.steps.contradiction_check import contradiction_check


def _chunk(content: str) -> Chunk:
    return Chunk(tenant_id=1, document_id=1, content=content, embedding=[0.0] * EMBEDDING_DIM)


def test_contradiction_check_adds_warning_for_conflicting_chunks() -> None:
    state = PipelineState(
        chunks=[
            _chunk("請求書の再発行は可能です。担当窓口に依頼してください。"),
            _chunk("請求書の再発行はできません。再発行は禁止です。"),
        ]
    )

    result = contradiction_check(state, {"warnings": {"contradiction": True}})

    assert len(result.warnings) == 1
    assert result.warnings[0].type == "contradiction"
    assert "矛盾" in result.warnings[0].message


def test_contradiction_check_skips_when_config_disables_it() -> None:
    state = PipelineState(
        chunks=[
            _chunk("請求書の再発行は可能です。"),
            _chunk("請求書の再発行はできません。"),
        ]
    )

    result = contradiction_check(state, {"warnings": {"contradiction": False}})

    assert result.warnings == []


def test_contradiction_check_does_not_mutate_input_state() -> None:
    state = PipelineState(
        chunks=[
            _chunk("契約変更は可能です。"),
            _chunk("契約変更は不可です。"),
        ]
    )

    contradiction_check(state, {"warnings": {"contradiction": True}})

    assert state.warnings == []
