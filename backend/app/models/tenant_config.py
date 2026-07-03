"""TenantConfig: per-tenant behavior stored as data, not code.

Holds the structured JSON described in multi-tenant-design.md §3 (search scope,
answer modes, pipeline, warnings, category policies, feedback). Exactly one row
per tenant, so ``tenant_id`` is unique.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models._common import TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class TenantConfig(TimestampMixin, Base):
    __tablename__ = "tenant_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Unique: one config row per tenant (multi-tenant-design.md "DBの1行").
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    # JSONB so config fields can be queried/indexed server-side later.
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    tenant: Mapped[Tenant] = relationship(back_populates="config")
