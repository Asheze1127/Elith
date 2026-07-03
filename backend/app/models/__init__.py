"""ORM models for the boundary design (tenant-scoped RAG data).

Importing this package registers every model on ``Base.metadata`` so that
Alembic autogenerate and metadata-level checks see all tables. Keep the star
imports below in sync with the modules in this package.
"""

from app.models.answer import Answer
from app.models.chunk import Chunk
from app.models.citation import Citation
from app.models.document import Document
from app.models.feedback import Feedback
from app.models.tenant import Tenant
from app.models.tenant_config import TenantConfig
from app.models.workspace import Workspace

__all__ = [
    "Answer",
    "Chunk",
    "Citation",
    "Document",
    "Feedback",
    "Tenant",
    "TenantConfig",
    "Workspace",
]
