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
