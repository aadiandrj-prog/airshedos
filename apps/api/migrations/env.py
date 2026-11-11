"""Explicit migration connection only. No .env loading or runtime auto-migration."""

import os

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

from app.persistence.models import Base

config = context.config
supplied_connection = config.attributes.get("connection")
if supplied_connection is not None:
    # The offline operator CLI has checked TLS, exact target/login, expected schema
    # and acquired its transaction lock. Application startup never calls this path.
    if config.attributes.get("seva_operator_migration") is not True:
        raise ValueError("Checked operator migration connection required")
    context.configure(
        connection=supplied_connection, target_metadata=Base.metadata, compare_type=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    url = os.environ.get("SEVA_MIGRATION_DATABASE_URL")
    if not url:
        raise ValueError(
            "SEVA_MIGRATION_DATABASE_URL must explicitly select the migration database"
        )
    parsed = make_url(url)
    if parsed.drivername != "postgresql+psycopg":
        raise ValueError("PostgreSQL with psycopg is required")
    if parsed.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Hosted migrations require the checked offline operator command")

    if context.is_offline_mode():
        context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = create_engine(
            parsed,
            poolclass=pool.NullPool,
            hide_parameters=True,
            connect_args={"connect_timeout": 5},
        )
        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=Base.metadata, compare_type=True
            )
            with context.begin_transaction():
                context.run_migrations()
        engine.dispose()
