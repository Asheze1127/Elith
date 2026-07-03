"""End-to-end tests for GET /tenant/config (app/api/tenant.py).

Wires the FastAPI app to the transactional db_session fixture (conftest.py)
via dependency_overrides, and overrides get_settings per-test to make the
local/non-local gate deterministic regardless of the worktree's backend/.env.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.main import app
from app.models.tenant import Tenant
from app.models.tenant_config import TenantConfig


@pytest.fixture()
def client(db_session):
    """TestClient whose DB dependency is the rolled-back db_session."""

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _use_environment(environment: str) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        ENVIRONMENT=environment, _env_file=None
    )


@pytest.fixture(autouse=True)
def _clear_settings_override():
    yield
    app.dependency_overrides.pop(get_settings, None)


def test_get_tenant_config_returns_config_json(client, db_session) -> None:
    _use_environment("local")
    tenant = Tenant(display_name="Test Co.")
    db_session.add(tenant)
    db_session.flush()
    db_session.add(TenantConfig(tenant_id=tenant.id, config={"display_name": "Test Co."}))
    db_session.flush()

    response = client.get("/tenant/config", headers={"X-Tenant-ID": str(tenant.id)})

    assert response.status_code == 200
    body = response.json()
    assert body == {"tenant_id": tenant.id, "config": {"display_name": "Test Co."}}


def test_get_tenant_config_unknown_tenant_returns_404_with_message(client) -> None:
    _use_environment("local")

    response = client.get("/tenant/config", headers={"X-Tenant-ID": "999999"})

    assert response.status_code == 404
    assert "999999" in response.json()["detail"]


def test_get_tenant_config_missing_header_returns_400(client) -> None:
    _use_environment("local")

    response = client.get("/tenant/config")

    assert response.status_code == 400


def test_get_tenant_config_non_integer_header_returns_400(client) -> None:
    _use_environment("local")

    response = client.get("/tenant/config", headers={"X-Tenant-ID": "abc"})

    assert response.status_code == 400


def test_get_tenant_config_non_local_rejects_header_with_501(client) -> None:
    _use_environment("production")

    response = client.get("/tenant/config", headers={"X-Tenant-ID": "1"})

    assert response.status_code == 501
