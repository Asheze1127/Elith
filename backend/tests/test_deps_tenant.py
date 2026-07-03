"""Tests for app.deps.tenant: tenant resolution + tenant_config loading.

get_tenant_id tests are header/settings gating only -- no DB needed.
get_tenant_config tests need db_session (see conftest.py) to read back a row
actually inserted into Postgres.
"""

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.deps.tenant import get_tenant_config, get_tenant_id
from app.models.tenant import Tenant
from app.models.tenant_config import TenantConfig


def _settings(environment: str) -> Settings:
    """Build Settings for a given ENVIRONMENT without reading backend/.env."""
    return Settings(ENVIRONMENT=environment, _env_file=None)


# --- get_tenant_id: local-only X-Tenant-ID gating --------------------------


def test_get_tenant_id_local_with_valid_header_returns_int() -> None:
    assert get_tenant_id(x_tenant_id="42", settings=_settings("local")) == 42


@pytest.mark.parametrize("environment", ["LOCAL", "Local", " local "])
def test_get_tenant_id_environment_compare_is_case_and_space_insensitive(
    environment: str,
) -> None:
    assert get_tenant_id(x_tenant_id="1", settings=_settings(environment)) == 1


def test_get_tenant_id_local_missing_header_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_tenant_id(x_tenant_id=None, settings=_settings("local"))
    assert exc_info.value.status_code == 400


def test_get_tenant_id_local_non_integer_header_raises_400() -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_tenant_id(x_tenant_id="not-a-number", settings=_settings("local"))
    assert exc_info.value.status_code == 400


def test_get_tenant_id_non_local_rejects_header_with_501() -> None:
    # Non-local has no session mechanism to fall back to (see module
    # docstring in app/deps/tenant.py): fail clearly rather than trust the
    # header as an unauthenticated identity claim.
    with pytest.raises(HTTPException) as exc_info:
        get_tenant_id(x_tenant_id="1", settings=_settings("production"))
    assert exc_info.value.status_code == 501


# --- get_tenant_config: DB read, scoped by tenant_id -----------------------


def test_get_tenant_config_returns_row_for_known_tenant(db_session) -> None:
    tenant = Tenant(display_name="Test Co.")
    db_session.add(tenant)
    db_session.flush()
    db_session.add(TenantConfig(tenant_id=tenant.id, config={"search": {"scope": "all"}}))
    db_session.flush()

    result = get_tenant_config(tenant_id=tenant.id, db=db_session)

    assert result.tenant_id == tenant.id
    assert result.config == {"search": {"scope": "all"}}


def test_get_tenant_config_unknown_tenant_raises_404_with_clear_message(db_session) -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_tenant_config(tenant_id=999_999, db=db_session)
    assert exc_info.value.status_code == 404
    assert "999999" in exc_info.value.detail


def test_get_tenant_config_tenant_without_config_row_raises_404(db_session) -> None:
    # A tenant can exist without ever having had a tenant_config row written
    # (e.g. mid-onboarding); this must 404 like an unknown tenant, not 500.
    tenant = Tenant(display_name="No Config Co.")
    db_session.add(tenant)
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        get_tenant_config(tenant_id=tenant.id, db=db_session)
    assert exc_info.value.status_code == 404


def test_get_tenant_config_does_not_leak_another_tenants_config(db_session) -> None:
    # Cross-tenant isolation (permission-design.md #3): resolving tenant A's
    # id must never return tenant B's config row, even when only B has one.
    tenant_a = Tenant(display_name="Tenant A")
    tenant_b = Tenant(display_name="Tenant B")
    db_session.add_all([tenant_a, tenant_b])
    db_session.flush()
    db_session.add(TenantConfig(tenant_id=tenant_b.id, config={"search": {"scope": "all"}}))
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        get_tenant_config(tenant_id=tenant_a.id, db=db_session)
    assert exc_info.value.status_code == 404

    # Sanity check: B's own config is still reachable via its own id.
    result = get_tenant_config(tenant_id=tenant_b.id, db=db_session)
    assert result.tenant_id == tenant_b.id
