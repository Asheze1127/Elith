"""Shared pytest fixtures.

test_models_scope.py and test_providers.py need no live DB (metadata-only /
network-free by design). Tests that exercise app.deps.tenant / GET
/tenant/config need a real Postgres+pgvector instance with migrations applied
(see the worktree setup notes: docker compose up -d db, then
`alembic upgrade head`).
"""

from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from app.core.db import get_engine, get_sessionmaker


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """A DB session bound to a connection whose transaction is rolled back.

    Every test gets a clean slate without needing to truncate tables: all
    writes happen inside one outer transaction that is rolled back at
    teardown, regardless of any commit/rollback the code under test performs
    on the session itself.
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
