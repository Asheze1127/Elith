"""Tenant-resolution FastAPI dependency (process-flow.md #1.1).

Depends only resolves *which* tenant this request belongs to and loads its
tenant_config row from the DB. No policy decision or prompt-building happens
here -- that is the common pipeline's job (multi-tenant-design.md #5):

    def get_tenant_config(tenant_id: str) -> TenantConfig:
        return repo.load_config(tenant_id)  # load one row from DB, nothing else

KNOWN LIMITATION / follow-up needed (flagged for the #6 PR description):
This codebase has no login/session mechanism yet -- Phase 0 (#2 FastAPI
foundation, #3 data models, #4 provider abstraction, #5 docker) does not add
one, and no auth-related issue exists elsewhere in the tracker. Resolving
tenant_id "from session", as the issue title literally asks, is therefore not
implementable today.

As a pragmatic MVP stand-in, tenant_id is resolved from an `X-Tenant-ID`
header, but that header is only ever honored when `ENVIRONMENT=local`
(mirrors the `_use_gemini` gate in app/providers/__init__.py). In any
non-local environment there is no session mechanism to fall back to, so the
request fails clearly (501) instead of silently trusting an unauthenticated
header as a tenant identity claim. A real session-based resolver needs its
own future issue.
"""

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.models.tenant_config import TenantConfig
from app.repository.tenant_config import get_tenant_config_by_tenant_id


def get_tenant_id(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    settings: Settings = Depends(get_settings),
) -> int:
    """Resolve the current request's tenant_id.

    MVP stand-in for real session-based resolution -- see module docstring
    for why this is `X-Tenant-ID` + a local-only gate rather than a session.
    """
    # strip()+lower() so 'LOCAL'/'Local'/' local ' behave like 'local', same as
    # the ENVIRONMENT compare in app.providers._use_gemini.
    if settings.ENVIRONMENT.strip().lower() != "local":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "Tenant resolution from session is not implemented yet. "
                "The X-Tenant-ID header fallback is only available when ENVIRONMENT=local."
            ),
        )

    if x_tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required 'X-Tenant-ID' header.",
        )

    try:
        return int(x_tenant_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'X-Tenant-ID' must be an integer tenant id, got {x_tenant_id!r}.",
        ) from exc


def get_tenant_config(
    tenant_id: int = Depends(get_tenant_id),
    db: Session = Depends(get_db),
) -> TenantConfig:
    """Load the resolved tenant's config row from the DB (one row, no logic)."""
    config = get_tenant_config_by_tenant_id(db, tenant_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No tenant_config found for tenant_id={tenant_id}.",
        )
    return config
