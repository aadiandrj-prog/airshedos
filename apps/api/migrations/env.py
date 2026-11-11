"""Explicit migration connection only. No .env loading or runtime auto-migration."""

import os

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

from app.persistence.models import Base

config = context.config
url = os.environ.get("SEVA_MIGRATION_DATABASE_URL")
if not url:
    raise ValueError("SEVA_MIGRATION_DATABASE_URL must explicitly select the migration database")
parsed = make_url(url)
if parsed.drivername != "postgresql+psycopg":
    raise ValueError("PostgreSQL with psycopg is required")
if parsed.host not in {"localhost", "127.0.0.1", "::1"}:
    # Phase 1 is local only; hosted migration authorization/rehearsal is a release gate.
    raise ValueError("Phase 1 migrations are restricted to local disposable PostgreSQL")

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(
        parsed, poolclass=pool.NullPool, hide_parameters=True, connect_args={"connect_timeout": 5}
    )
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
