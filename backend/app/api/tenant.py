"""GET /tenant/config: return the resolved tenant's config as data.

No tenant-specific branching lives here -- the response is a thin pass-through
of the JSONB `config` blob loaded by app.deps.tenant.get_tenant_config
(multi-tenant-design.md: customer differences are data, not code).
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.deps.tenant import get_tenant_config
from app.models.tenant_config import TenantConfig

router = APIRouter()


class TenantConfigResponse(BaseModel):
    """Response shape for GET /tenant/config.

    `tenant_id` is the DB row's integer id (app.models.tenant.Tenant.id).
    This is deliberately kept distinct from any string identifier that may
    also live inside `config` (multi-tenant-design.md's sample schema shows a
    human-readable "tenant_id" slug as one of the free-form config fields) --
    the two are not guaranteed to match.
    """

    tenant_id: int
    config: dict[str, Any]


@router.get("/tenant/config", response_model=TenantConfigResponse)
def read_tenant_config(config: TenantConfig = Depends(get_tenant_config)) -> TenantConfigResponse:
    """Return the current tenant's config. Tenant resolution is entirely in Depends."""
    return TenantConfigResponse(tenant_id=config.tenant_id, config=config.config)
