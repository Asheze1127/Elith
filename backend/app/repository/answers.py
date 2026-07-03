"""Tenant-scoped persistence for generated answers and citations."""

from sqlalchemy.orm import Session

from app.models.answer import Answer
from app.models.chunk import Chunk
from app.models.citation import Citation
from app.models.document import Document
from app.rag.steps import CitationDraft


class CitationScopeError(Exception):
    """Raised when a citation draft references another tenant's source row."""


def create_answer_with_citations(
    db: Session,
    *,
    tenant_id: int,
    query: str,
    body: str,
    status: str,
    mode: str | None,
    citation_drafts: list[CitationDraft],
) -> Answer:
    """Persist one Answer and its Citation rows after tenant-boundary checks."""
    _ensure_citations_belong_to_tenant(db, tenant_id=tenant_id, citation_drafts=citation_drafts)

    answer = Answer(
        tenant_id=tenant_id,
        query=query,
        body=body,
        status=status,
        mode=mode,
    )
    answer.citations = [
        Citation(
            chunk_id=draft.chunk_id,
            document_id=draft.document_id,
            snippet=draft.snippet,
            source_uri=draft.source_uri,
            source_updated_at=draft.source_updated_at,
        )
        for draft in citation_drafts
    ]
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return answer


def _ensure_citations_belong_to_tenant(
    db: Session,
    *,
    tenant_id: int,
    citation_drafts: list[CitationDraft],
) -> None:
    for draft in citation_drafts:
        if draft.chunk_id is not None:
            chunk = db.get(Chunk, draft.chunk_id)
            if chunk is None or chunk.tenant_id != tenant_id:
                raise CitationScopeError(
                    f"citation chunk '{draft.chunk_id}' does not belong to tenant '{tenant_id}'"
                )
        if draft.document_id is not None:
            document = db.get(Document, draft.document_id)
            if document is None or document.tenant_id != tenant_id:
                raise CitationScopeError(
                    f"citation document '{draft.document_id}' does not belong to "
                    f"tenant '{tenant_id}'"
                )
