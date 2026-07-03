"""Alembic environment.

Wired to the app's Base.metadata and DATABASE_URL so ``--autogenerate`` sees
every ORM model and migrations target the same DB as the running app.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Importing the models package has the side effect of registering every table
# on Base.metadata, which autogenerate needs. Kept with the app imports.
import app.models  # noqa: F401
from app.core.config import get_settings
from app.core.db import Base

# Alembic Config object, providing access to values within the .ini file.
config = context.config

# Inject the app's DATABASE_URL so alembic.ini carries no connection string
# (and no secrets). Overridable via a real sqlalchemy.url in the .ini if set.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().DATABASE_URL)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for 'autogenerate' support.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DBAPI connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
