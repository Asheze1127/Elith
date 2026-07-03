"""Document ingestion and listing endpoints (/documents).

tenant_id is accepted explicitly as a request field for now: tenant resolution
via Depends (app/deps/tenant.py, directory.md) is a separate, concurrently
developed issue this endpoint does not depend on yet.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.document import Document
from app.repository.documents import (
    TenantNotFoundError,
    WorkspaceMismatchError,
    list_documents,
)
from ingestion.pipeline import EmbeddingProviderError, EmptyDocumentError, ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentIngestRequest(BaseModel):
    """Body for POST /documents.

    ``title`` requires at least one non-whitespace character via
    ``min_length=1``; FastAPI turns a violation into a 422 automatically, so
    invalid title input is rejected without any custom error handling.
    """

    tenant_id: int
    title: str = Field(min_length=1)
    content: str
    workspace_id: int | None = None
    source_uri: str | None = None
    source_updated_at: datetime | None = None


class DocumentResponse(BaseModel):
    id: int
    tenant_id: int
    workspace_id: int | None
    title: str
    source_uri: str | None
    chunk_count: int
    created_at: datetime

    @classmethod
    def from_model(cls, document: Document) -> "DocumentResponse":
        return cls(
            id=document.id,
            tenant_id=document.tenant_id,
            workspace_id=document.workspace_id,
            title=document.title,
            source_uri=document.source_uri,
            chunk_count=len(document.chunks),
            created_at=document.created_at,
        )


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    payload: DocumentIngestRequest, db: Session = Depends(get_db)
) -> DocumentResponse:
    """Ingest one document: split into chunks, embed, and persist."""
    try:
        document = ingest_document(
            db,
            tenant_id=payload.tenant_id,
            title=payload.title,
            content=payload.content,
            workspace_id=payload.workspace_id,
            source_uri=payload.source_uri,
            source_updated_at=payload.source_updated_at,
        )
    except EmptyDocumentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except TenantNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except WorkspaceMismatchError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except EmbeddingProviderError as exc:
        # Upstream/provider failure: surface a clear message, never a raw
        # stack trace or SDK-internal detail (process-flow.md §5.3).
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return DocumentResponse.from_model(document)


@router.get("", response_model=list[DocumentResponse])
def get_documents(
    tenant_id: int = Query(..., description="Tenant to scope the listing to"),
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    """List a tenant's ingested documents, oldest first."""
    documents = list_documents(db, tenant_id=tenant_id)
    return [DocumentResponse.from_model(document) for document in documents]
