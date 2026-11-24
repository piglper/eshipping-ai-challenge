"""Alembic environment: the schema is the one the application defines."""

import os

from alembic import context
from sqlalchemy import create_engine

from eshipping_ai.adapters.sql_schema import metadata

DEFAULT_URL = "sqlite:///data/output/eshipping.db"


def database_url() -> str:
    """URL of the database to migrate: the Alembic option, the environment or the default."""
    return (
        context.config.get_main_option("sqlalchemy.url")
        or os.environ.get("ESHIPPING_DATABASE_URL")
        or DEFAULT_URL
    )


def run_migrations_offline() -> None:
    """Emit the SQL without connecting to the database."""
    context.configure(
        url=database_url(), target_metadata=metadata, literal_binds=True, render_as_batch=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Migrate the database, in one transaction."""
    engine = create_engine(database_url())
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=metadata, render_as_batch=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
