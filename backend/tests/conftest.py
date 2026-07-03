"""Shared pytest fixtures for DB-backed tests.

test_models_scope.py and test_providers.py need no live DB (metadata-only /
network-free by design). Tests that exercise a real Postgres+pgvector
instance (app.deps.tenant, ingestion, retrieve, ...) use ``db_session``
below (see the worktree setup notes: docker compose up -d db, then
`alembic upgrade head`).
"""

from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from app.core.db import get_engine, get_sessionmaker
from app.models.tenant import Tenant


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """A DB session bound to a connection whose transaction is rolled back.

    Every test gets a clean slate without needing to truncate tables: all
    writes happen inside one outer transaction that is rolled back at
    teardown, regardless of any commit/rollback the code under test performs
    on the session itself (SQLAlchemy nests an inner commit as a savepoint
    release when it runs inside an already-begun outer transaction).
    """
    engine = get_engine()
    connection = engine.connect()
    transaction = connection.begin()
    session_factory = get_sessionmaker()
    session = session_factory(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def make_tenant(db_session: Session):
    """Factory fixture: create a Tenant row scoped to this test's session.

    No explicit teardown/delete is needed: ``db_session``'s outer transaction
    rollback (above) discards every row created through it, including any
    committed by the code under test.
    """

    def _make(display_name: str = "Test Tenant") -> Tenant:
        tenant = Tenant(display_name=display_name)
        db_session.add(tenant)
        db_session.commit()
        db_session.refresh(tenant)
        return tenant

    return _make
