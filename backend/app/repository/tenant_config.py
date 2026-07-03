"""Tenant-config data access.

All lookups are scoped by ``tenant_id`` (permission-design.md #3, "データ境界").
The resolved tenant_id from app.deps.tenant is the only intended source of the
tenant_id argument here -- callers must never forward an arbitrary/unscoped
filter from request input.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant_config import TenantConfig


def get_tenant_config_by_tenant_id(db: Session, tenant_id: int) -> TenantConfig | None:
    """Return the single tenant_config row for tenant_id, or None if missing.

    tenant_config.tenant_id is unique (one row per tenant), so at most one
    result is possible.
    """
    stmt = select(TenantConfig).where(TenantConfig.tenant_id == tenant_id)
    return db.execute(stmt).scalar_one_or_none()
