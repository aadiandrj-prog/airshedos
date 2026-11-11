"""Explicit operator-only hosted migration command; never called by application startup."""

import argparse
import os
import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, pool, text
from sqlalchemy.engine import URL, make_url

from app.persistence.database import SCHEMA_REVISION


class MigrationRefused(ValueError):
    """Safe reason code only: never include a connection string or server exception."""


def checked_target(url: str, *, host: str, database: str, role: str, revision: str) -> URL:
    try:
        parsed = make_url(url)
    except Exception:
        raise MigrationRefused("MIGRATION_URL_INVALID") from None
    if parsed.drivername != "postgresql+psycopg":
        raise MigrationRefused("MIGRATION_POSTGRES_REQUIRED")
    if (
        not host
        or not database
        or not role
        or (parsed.host, parsed.database, parsed.username)
        != (
            host,
            database,
            role,
        )
    ):
        raise MigrationRefused("MIGRATION_TARGET_MISMATCH")
    if revision != "empty" and not re.fullmatch(r"seva_\d{4}", revision):
        raise MigrationRefused("MIGRATION_EXPECTED_REVISION_REQUIRED")
    if set(parsed.query) - {"sslmode", "sslrootcert", "channel_binding", "gssencmode"}:
        raise MigrationRefused("MIGRATION_CONNECTION_OVERRIDES_REFUSED")
    if parsed.query.get("gssencmode", "disable") != "disable":
        raise MigrationRefused("MIGRATION_TLS_REQUIRED")
    if host not in {"localhost", "127.0.0.1", "::1"}:
        if parsed.query.get("sslmode") != "verify-full" or not parsed.password:
            raise MigrationRefused("MIGRATION_VERIFIED_TLS_AND_EXPLICIT_LOGIN_REQUIRED")
        ca = parsed.query.get("sslrootcert")
        if not isinstance(ca, str) or not (
            ca == "system" or (Path(ca).is_absolute() and Path(ca).is_file())
        ):
            raise MigrationRefused("MIGRATION_CA_REQUIRED")
        if "-pooler." in host or not re.fullmatch(r"[A-Za-z0-9.-]+", host):
            raise MigrationRefused("MIGRATION_DIRECT_HOST_REQUIRED")
    return parsed.update_query_dict({"gssencmode": "disable"})


def migrate(url: str, *, host: str, database: str, role: str, revision: str):
    target = checked_target(url, host=host, database=database, role=role, revision=revision)
    engine = create_engine(
        target,
        poolclass=pool.NullPool,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 10,
            "options": "-c statement_timeout=60000 -c lock_timeout=5000",
        },
    )
    try:
        with engine.begin() as connection:
            actual = tuple(
                connection.execute(
                    text("SELECT current_database(), session_user, current_user")
                ).one()
            )
            if actual != (database, role, role):
                raise MigrationRefused("MIGRATION_CONNECTED_IDENTITY_MISMATCH")
            connection.execute(text("SET LOCAL search_path = public"))
            connection.execute(text("SET LOCAL lock_timeout = '5s'"))
            connection.execute(text("SET LOCAL statement_timeout = '60s'"))
            if not connection.scalar(text("SELECT pg_try_advisory_xact_lock(732008420022)")):
                raise MigrationRefused("MIGRATION_ALREADY_RUNNING")
            if revision == "empty":
                # Refuse other applications' schemas too; this is an isolated pilot target.
                if connection.scalar(
                    text("""SELECT EXISTS (
                      SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                      WHERE n.nspname NOT IN ('pg_catalog','information_schema')
                      AND n.nspname NOT LIKE 'pg_toast%'
                      AND c.relkind IN ('r','p','v','m','S','f'))""")
                ):
                    raise MigrationRefused("MIGRATION_DATABASE_NOT_EMPTY")
            else:
                if "alembic_version" not in inspect(connection).get_table_names(schema="public"):
                    raise MigrationRefused("MIGRATION_REVISION_MISMATCH")
                revisions = list(
                    connection.scalars(text("SELECT version_num FROM alembic_version"))
                )
                if revisions != [revision]:
                    raise MigrationRefused("MIGRATION_REVISION_MISMATCH")
            config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
            config.attributes["connection"] = connection
            config.attributes["seva_operator_migration"] = True
            command.upgrade(config, "head")
            if (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                != SCHEMA_REVISION
            ):
                raise MigrationRefused("MIGRATION_HEAD_MISMATCH")
            # All checks and DDL commit together; failures roll back the entire command.
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--operator-role", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--acknowledge-target", action="store_true", required=True)
    args = parser.parse_args()
    url = os.environ.get("SEVA_MIGRATION_DATABASE_URL")
    if not url:
        parser.exit(1, "MIGRATION_URL_REQUIRED: supply the secret through the environment.\n")
    try:
        migrate(
            url,
            host=args.host,
            database=args.database,
            role=args.operator_role,
            revision=args.expected_revision,
        )
    except MigrationRefused as error:
        parser.exit(1, f"{error}\n")
    except Exception:
        parser.exit(1, "MIGRATION_DATABASE_ERROR: no target or credential details printed.\n")
    print("Schema upgrade complete. Pilot access remains subject to release and identity checks.")


if __name__ == "__main__":
    main()
