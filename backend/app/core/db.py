"""Database access layer (SQLAlchemy 2.0 style).

The engine is created lazily so that importing this module and booting the app
does not require a live database. /health must never touch the DB.
"""

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for ORM models (defined by later issues)."""


# Lazily-initialized singletons; created on first DB access, not at import time.
_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Create (once) and return the SQLAlchemy engine for the configured DB."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    """Create (once) and return the session factory bound to the engine."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a session and closing it afterwards."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()
