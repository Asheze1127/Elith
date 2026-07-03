"""Tests for stale_warning: old source material produces a typed warning."""

from datetime import UTC, datetime, timedelta

from app.models.chunk import EMBEDDING_DIM, Chunk
from app.models.document import Document
from app.rag.steps import PipelineState
from app.rag.steps.stale_warning import STALE_SOURCE_MAX_AGE_DAYS, stale_warning


def _chunk_with_document(source_updated_at: datetime | None) -> Chunk:
    document = Document(
        tenant_id=1,
        title="Outdated billing guide",
        source_updated_at=source_updated_at,
    )
    return Chunk(
        tenant_id=1,
        document=document,
        content="請求書の再発行は旧フォームで申請します。",
        embedding=[0.0] * EMBEDDING_DIM,
    )


def test_stale_warning_adds_warning_for_old_source() -> None:
    old_source = datetime.now(UTC) - timedelta(days=STALE_SOURCE_MAX_AGE_DAYS + 1)
    state = PipelineState(chunks=[_chunk_with_document(old_source)])

    result = stale_warning(state, {"warnings": {"stale_sources": True}})

    assert len(result.warnings) == 1
    assert result.warnings[0].type == "stale_sources"
    assert "Outdated billing guide" in result.warnings[0].message


def test_stale_warning_skips_when_config_disables_it() -> None:
    old_source = datetime.now(UTC) - timedelta(days=STALE_SOURCE_MAX_AGE_DAYS + 1)
    state = PipelineState(chunks=[_chunk_with_document(old_source)])

    result = stale_warning(state, {"warnings": {"stale_sources": False}})

    assert result.warnings == []


def test_stale_warning_does_not_mutate_input_state() -> None:
    old_source = datetime.now(UTC) - timedelta(days=STALE_SOURCE_MAX_AGE_DAYS + 1)
    state = PipelineState(chunks=[_chunk_with_document(old_source)])

    stale_warning(state, {"warnings": {"stale_sources": True}})

    assert state.warnings == []
