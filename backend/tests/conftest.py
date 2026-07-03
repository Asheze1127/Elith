"""Shared pytest fixtures for DB-backed tests.

Uses the local Postgres+pgvector instance configured via backend/.env
(DATABASE_URL) -- the same DB migrations run against. Each test creates its
own tenant row(s) via ``make_tenant`` and they are deleted (cascading to any
workspace/document/chunk rows) during teardown, so tests stay independent of
execution order and do not leave rows behind.
"""

import pytest
from sqlalchemy.orm import Session

from app.core.db import get_sessionmaker
from app.models.tenant import Tenant


@pytest.fixture
def db_session() -> Session:
    """A DB session bound to the configured test database, closed after use."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def make_tenant(db_session: Session):
    """Factory fixture: create a Tenant row; delete it (cascade) on teardown."""
    created: list[Tenant] = []

    def _make(display_name: str = "Test Tenant") -> Tenant:
        tenant = Tenant(display_name=display_name)
        db_session.add(tenant)
        db_session.commit()
        db_session.refresh(tenant)
        created.append(tenant)
        return tenant

    yield _make

    for tenant in created:
        db_session.delete(tenant)
    db_session.commit()
