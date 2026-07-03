"""POST /chat: tenant_config -> shared RAG pipeline -> persisted answer."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.deps.tenant import get_tenant_config
from app.models.document import Document
from app.models.tenant_config import TenantConfig
from app.rag.pipeline import LLMProviderError, PipelineError, run_pipeline
from app.rag.retrieve import EmbeddingProviderError
from app.rag.steps import CitationDraft
from app.repository.answers import CitationScopeError, create_answer_with_citations

router = APIRouter(prefix="/chat", tags=["chat"])

# Keeps an accidental paste of a huge document from being sent through the
# synchronous chat path; larger inputs should become a separate upload flow.
MAX_QUERY_CHARS = 4_000


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)
    mode: str | None = None
    workspace_id: int | None = None

    @field_validator("query")
    @classmethod
    def _query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must contain at least one non-whitespace character")
        return value


class WarningResponse(BaseModel):
    type: str
    message: str


class CitationResponse(BaseModel):
    chunk_id: int | None
    document_id: int | None
    title: str | None
    snippet: str | None
    source_uri: str | None
    source_updated_at: datetime | None


class ChatResponse(BaseModel):
    answer_id: int
    answer: str
    citations: list[CitationResponse]
    status: str
    warnings: list[WarningResponse]


@router.post("", response_model=ChatResponse)
def create_chat_answer(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    tenant_config: TenantConfig = Depends(get_tenant_config),
) -> ChatResponse:
    """Run the shared RAG pipeline for the resolved tenant and return its answer."""
    config = tenant_config.config
    mode = _resolve_mode(config, payload.mode)

    # Do not mutate tenant_config.config (JSONB row); build a shallow copy for prompt/pipeline.
    config_for_pipeline = config
    if mode is not None:
        answer_cfg = config.get("answer")
        if isinstance(answer_cfg, dict):
            config_for_pipeline = {**config, "answer": {**answer_cfg, "default_mode": mode}}

    try:
        result = run_pipeline(
            db,
            tenant_id=tenant_config.tenant_id,
            query=payload.query,
            config=config_for_pipeline,
            workspace_id=payload.workspace_id,
            mode=mode,
        )
        answer = create_answer_with_citations(
            db,
            tenant_id=tenant_config.tenant_id,
            query=payload.query,
            body=result.answer,
            status=result.status,
            mode=mode,
            citation_drafts=result.citations,
        )
    except EmbeddingProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="質問の検索準備に失敗しました。時間をおいて再度お試しください。",
        ) from exc
    except LLMProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="回答生成に失敗しました。時間をおいて再度お試しください。",
        ) from exc
    except PipelineError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"チャット設定に未対応の処理があります。管理者に連絡してください。({exc})",
        ) from exc
    except CitationScopeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="回答の引用情報を保存できませんでした。管理者に連絡してください。",
        ) from exc

    return ChatResponse(
        answer_id=answer.id,
        answer=result.answer,
        citations=[
            _citation_response(db, tenant_id=tenant_config.tenant_id, draft=draft)
            for draft in result.citations
        ],
        status=result.status,
        warnings=[
            WarningResponse(type=warning.type, message=warning.message)
            for warning in result.warnings
        ],
    )


def _resolve_mode(config: dict[str, Any], requested_mode: str | None) -> str | None:
    answer_config = config.get("answer")
    answer = answer_config if isinstance(answer_config, dict) else {}
    modes_value = answer.get("modes")
    modes = (
        [mode for mode in modes_value if isinstance(mode, str)]
        if isinstance(modes_value, list)
        else []
    )

    if requested_mode is not None:
        if modes and requested_mode not in modes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"mode '{requested_mode}' is not allowed for this tenant.",
            )
        return requested_mode

    default_mode = answer.get("default_mode")
    if isinstance(default_mode, str):
        return default_mode
    return modes[0] if modes else None


def _citation_response(db: Session, *, tenant_id: int, draft: CitationDraft) -> CitationResponse:
    document = db.get(Document, draft.document_id) if draft.document_id is not None else None
    if document is not None and document.tenant_id != tenant_id:
        document = None

    return CitationResponse(
        chunk_id=draft.chunk_id,
        document_id=draft.document_id,
        title=document.title if document is not None else None,
        snippet=draft.snippet,
        source_uri=draft.source_uri,
        source_updated_at=draft.source_updated_at,
    )
