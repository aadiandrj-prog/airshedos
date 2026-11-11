"""Hosted-command guards; integration uses only a named disposable loopback database."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.persistence import migrate as tool
from app.persistence.models import Base

API_ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_URL = (
    "postgresql+psycopg://pilot_operator:synthetic-only@ep-pilot.example.invalid/pilot"
    "?sslmode=verify-full&sslrootcert=system"
)
TARGET = dict(
    host="ep-pilot.example.invalid", database="pilot", role="pilot_operator", revision="empty"
)


@pytest.mark.parametrize(
    ("url", "fields", "reason"),
    [
        (SYNTHETIC_URL, {"host": "other.example.invalid"}, "TARGET_MISMATCH"),
        (SYNTHETIC_URL, {"database": "other"}, "TARGET_MISMATCH"),
        (SYNTHETIC_URL, {"role": "app_runtime"}, "TARGET_MISMATCH"),
        (SYNTHETIC_URL, {"revision": "head"}, "EXPECTED_REVISION"),
        (SYNTHETIC_URL.replace("verify-full", "require"), {}, "VERIFIED_TLS"),
        (SYNTHETIC_URL.replace("&sslrootcert=system", ""), {}, "CA_REQUIRED"),
        (SYNTHETIC_URL + "&host=other.example.invalid", {}, "OVERRIDES_REFUSED"),
        (SYNTHETIC_URL + "&service=other", {}, "OVERRIDES_REFUSED"),
        (SYNTHETIC_URL + "&options=-crole=other", {}, "OVERRIDES_REFUSED"),
        (
            SYNTHETIC_URL.replace("ep-pilot.", "ep-pilot-pooler."),
            {"host": "ep-pilot-pooler.example.invalid"},
            "DIRECT_HOST",
        ),
        (SYNTHETIC_URL.replace("postgresql+psycopg", "postgresql"), {}, "POSTGRES_REQUIRED"),
    ],
)
def test_checked_hosted_target_fails_before_any_connection(monkeypatch, url, fields, reason):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Invalid targets must not open any connection")

    monkeypatch.setattr(tool, "create_engine", forbidden)
    with pytest.raises(tool.MigrationRefused, match=reason) as error:
        tool.migrate(url, **(TARGET | fields))
    assert "synthetic-only" not in str(error.value)
    assert "example.invalid" not in str(error.value)


def test_explicit_hosted_target_accepts_verified_tls_but_plain_alembic_refuses():
    assert tool.checked_target(SYNTHETIC_URL, **TARGET).query["sslmode"] == "verify-full"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_ROOT,
        env={**os.environ, "SEVA_MIGRATION_DATABASE_URL": SYNTHETIC_URL},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Hosted migrations require the checked offline operator command" in result.stderr
    assert "synthetic-only" not in result.stderr


@pytest.fixture
def target_database():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Real PostgreSQL test requires explicit TEST_DATABASE_URL")
    parsed = make_url(url)
    if (parsed.host, parsed.database, parsed.username) != (
        "127.0.0.1",
        "seva_phase1_test",
        "seva_test",
    ):
        pytest.fail("Only the named disposable loopback database may create this fixture")
    admin = create_engine(parsed, isolation_level="AUTOCOMMIT", hide_parameters=True)
    name = "seva_migration_test"
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield parsed.set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def local_target(revision="empty"):
    return dict(
        host="127.0.0.1", database="seva_migration_test", role="seva_test", revision=revision
    )


def test_real_postgres_migration_is_atomic_and_rejects_wrong_revision(target_database, monkeypatch):
    engine = create_engine(target_database, hide_parameters=True)
    upgrade = tool.command.upgrade

    def interrupted(config, _revision):
        config.attributes["connection"].execute(text("CREATE TABLE rollback_probe(id integer)"))
        raise RuntimeError("Synthetic migration interruption")

    monkeypatch.setattr(tool.command, "upgrade", interrupted)
    with pytest.raises(RuntimeError, match="Synthetic migration interruption"):
        tool.migrate(target_database, **local_target())
    with engine.connect() as connection:
        assert inspect(connection).get_table_names() == []
    monkeypatch.setattr(tool.command, "upgrade", upgrade)
    tool.migrate(target_database, **local_target())
    with engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) == set(Base.metadata.tables) | {
            "alembic_version"
        }
        assert connection.scalar(text("SELECT state FROM recovery_control")) == "QUARANTINED"
    with pytest.raises(tool.MigrationRefused, match="DATABASE_NOT_EMPTY"):
        tool.migrate(target_database, **local_target())
    with pytest.raises(tool.MigrationRefused, match="REVISION_MISMATCH"):
        tool.migrate(target_database, **local_target("seva_0001"))
    tool.migrate(target_database, **local_target("seva_0006"))
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(732008420022)"))
        with pytest.raises(tool.MigrationRefused, match="ALREADY_RUNNING"):
            tool.migrate(target_database, **local_target("seva_0006"))
    engine.dispose()


def test_initial_setup_refuses_an_unrelated_nonpublic_schema(target_database):
    engine = create_engine(target_database, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(text("CREATE SCHEMA another_app"))
        connection.execute(text("CREATE TABLE another_app.existing_content(id integer)"))
    with pytest.raises(tool.MigrationRefused, match="DATABASE_NOT_EMPTY"):
        tool.migrate(target_database, **local_target())
    with engine.connect() as connection:
        assert "existing_content" in inspect(connection).get_table_names(schema="another_app")
        assert inspect(connection).get_table_names(schema="public") == []
    engine.dispose()
