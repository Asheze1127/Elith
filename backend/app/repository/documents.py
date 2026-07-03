"""Tenant-scoped data access for documents and their chunks.

Every read/write here takes an explicit ``tenant_id`` and never reaches across
tenant boundaries (permission-design.md §3): listing filters by it, and
creation validates it (and workspace ownership) before writing a single row.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.tenant import Tenant
from app.models.workspace import Workspace


class TenantNotFoundError(Exception):
    """Raised when the given tenant_id does not reference an existing tenant."""


class WorkspaceMismatchError(Exception):
    """Raised when workspace_id exists but belongs to a different tenant.

    Document.workspace_id has no DB-level composite FK enforcing this (see the
    comment on app.models.document.Document.workspace_id), so it must be
    checked here before a document is written.
    """


def _ensure_tenant_exists(db: Session, tenant_id: int) -> None:
    if db.get(Tenant, tenant_id) is None:
        raise TenantNotFoundError(f"tenant '{tenant_id}' does not exist")


def _ensure_workspace_belongs_to_tenant(db: Session, tenant_id: int, workspace_id: int) -> None:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None or workspace.tenant_id != tenant_id:
        raise WorkspaceMismatchError(
            f"workspace '{workspace_id}' does not belong to tenant '{tenant_id}'"
        )


def create_document(
    db: Session,
    *,
    tenant_id: int,
    title: str,
    chunk_texts: list[str],
    chunk_embeddings: list[list[float]],
    workspace_id: int | None = None,
    source_uri: str | None = None,
    source_updated_at: datetime | None = None,
) -> Document:
    """Persist a Document plus its Chunk rows, scoped to ``tenant_id``.

    Validates tenant (and, if given, workspace) existence/ownership first, so
    an invalid tenant_id/workspace_id never results in a partially-written
    document.
    """
    _ensure_tenant_exists(db, tenant_id)
    if workspace_id is not None:
        _ensure_workspace_belongs_to_tenant(db, tenant_id, workspace_id)

    document = Document(
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        title=title,
        source_uri=source_uri,
        source_updated_at=source_updated_at,
    )
    # tenant_id is denormalized onto Chunk (see app.models.chunk) so every chunk
    # row is directly tenant-scopable without joining back through document.
    document.chunks = [
        Chunk(tenant_id=tenant_id, content=text, embedding=embedding)
        for text, embedding in zip(chunk_texts, chunk_embeddings, strict=True)
    ]
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def list_documents(db: Session, *, tenant_id: int) -> list[Document]:
    """List a tenant's documents, oldest first, with chunks eagerly loaded."""
    stmt = (
        select(Document)
        .where(Document.tenant_id == tenant_id)
        .options(selectinload(Document.chunks))
        .order_by(Document.created_at)
    )
    return list(db.scalars(stmt).all())
