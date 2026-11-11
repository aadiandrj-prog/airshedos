"""Actual PG18 archive -> separate DB; never overwrite source, live records or stores."""

import json
import os
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from test_access import access_fixture as access_fixture
from test_access import fixture as fixture
from test_access import persistence_fixture as persistence_fixture
from test_access import pg as pg
from test_access import signing_key as signing_key
from test_citizen import output as output
from test_persistence import OTHER, RESIDENT, REVIEWER, submission
from test_processing import worker

from app.operations.recovery import RecoveryManager, read_manifest, write_manifest
from app.persistence.contracts import AccessDenied, NotFound, PersistenceError
from app.persistence.database import database
from app.persistence.media import LocalPrivateMediaStore, PrivateMediaService
from app.persistence.models import (
    AuthSession,
    AuthSessionSecret,
    EvidenceFragment,
    Identity,
    Job,
    Media,
    Membership,
    RecoveryControl,
    Report,
)
from app.persistence.repository import DurableRepository


def container():
    name = os.getenv("SEVA_TEST_PG_CONTAINER")
    if not name or not all(c.isalnum() or c in "-_" for c in name):
        pytest.fail("Real restore gate requires explicit disposable SEVA_TEST_PG_CONTAINER")
    # Independently verify container database and user; never accept an arbitrary host target.
    check = subprocess.run(
        [
            "docker",
            "exec",
            name,
            "psql",
            "-U",
            "seva_test",
            "-d",
            "seva_phase1_test",
            "-Atc",
            "SELECT current_database()",
        ],
        capture_output=True,
        check=True,
    )
    assert check.stdout.strip() == b"seva_phase1_test"
    return name


def test_isolated_archive_restore_replays_post_backup_deletions_and_revocations(
    access_fixture, tmp_path, output
):
    f = access_fixture
    f["repo"].clock = lambda: datetime.now(UTC)
    old_epoch = uuid4()
    with f["sessions"].begin() as session:
        row = session.get(RecoveryControl, "pilot")
        row.epoch, row.state = old_epoch, "READY"
    f["repo"].release_epoch = old_epoch
    extra = f["repo"].create_report(
        f["principals"][RESIDENT.subject],
        submission(),
        key=uuid4(),
        key_created_at=datetime.now(UTC),
    )
    import asyncio

    synthetic_worker = worker(f, output)
    for receipt in (f["a"], f["b"]):
        lease = synthetic_worker.queue.claim(report_id=receipt.report_id)
        asyncio.run(synthetic_worker.execute(lease))
    with f["sessions"].begin() as session:
        session.add(
            AuthSessionSecret(
                session_id=f["session_ids"][RESIDENT.subject],
                sealed_data=b"synthetic-ciphertext-not-a-real-token",
            )
        )
    archived_store = LocalPrivateMediaStore((tmp_path / "restored-objects").resolve())
    for key, _ in f["store"].inventory():
        archived_store.put_derivative(key, f["store"].read(key))
    pg = container()
    started = time.perf_counter()
    with f["sessions"]() as session:
        backup_at = session.scalar(select(func.clock_timestamp()))
    archive = subprocess.run(
        [
            "docker",
            "exec",
            pg,
            "pg_dump",
            "-U",
            "seva_test",
            "-d",
            "seva_phase1_test",
            "-Fc",
            "--no-owner",
            "--no-privileges",
        ],
        capture_output=True,
        check=True,
    ).stdout
    dump_seconds = time.perf_counter() - started
    f["repo"].delete_report(f["principals"][RESIDENT.subject], f["a"].report_id)
    with f["sessions"].begin() as session:
        session.get(Media, f["media_b"]).state = "DELETING"
        session.get(Report, extra.report_id).content_expires_at = datetime.now(UTC) - timedelta(
            seconds=1
        )
        session.get(Identity, f["users"][REVIEWER.subject]).active = False
    source_manager = RecoveryManager(f["repo"], f["store"], database_role="seva_test")
    manifest = source_manager.export()
    private = tmp_path / "private-ledger"
    private.mkdir(mode=0o700)
    manifest_path = private / "manifest.json"
    digest = write_manifest(manifest_path, manifest)
    assert read_manifest(manifest_path, digest) == manifest
    assert (
        b"description" not in manifest_path.read_bytes()
        and b"latitude" not in manifest_path.read_bytes()
    )
    with pytest.raises(ValueError):
        read_manifest(manifest_path, "0" * 64)
    target = make_url(f["url"]).set(database="seva_restore_test")
    with f["engine"].connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("CREATE DATABASE seva_restore_test"))
    engine = None
    try:
        started = time.perf_counter()
        subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                pg,
                "pg_restore",
                "-U",
                "seva_test",
                "-d",
                "seva_restore_test",
                "--no-owner",
                "--no-privileges",
                "--exit-on-error",
            ],
            input=archive,
            capture_output=True,
            check=True,
        )
        restore_seconds = time.perf_counter() - started
        engine, sessions = database(target.render_as_string(hide_password=False))
        new_epoch = uuid4()
        repo = DurableRepository(sessions, release_epoch=new_epoch)
        manager = RecoveryManager(repo, archived_store, database_role="seva_test")
        # Before quarantine is even applied, a different external epoch blocks reads.
        with pytest.raises(PersistenceError):
            repo.resident_detail(RESIDENT, f["a"].report_id)
        with sessions() as session:
            assert session.scalar(select(func.count()).select_from(AuthSessionSecret)) == 1
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(EvidenceFragment)
                    .where(EvidenceFragment.payload.is_not(None))
                )
                >= 2
            )
        manager.quarantine(new_epoch)
        with pytest.raises(AccessDenied):
            manager.release(new_epoch, expected_sha256=digest)
        with pytest.raises(AccessDenied):
            manager.initialise_empty(uuid4())
        stale = manifest.model_copy(
            update={"created_at": datetime.now(UTC) - timedelta(minutes=10)}
        )
        with pytest.raises(AccessDenied):
            manager.apply(new_epoch, stale, backup_at=backup_at, expected_sha256=digest)
        with pytest.raises(ValueError):
            manager.apply(new_epoch, manifest, backup_at=backup_at, expected_sha256="0" * 64)
        incomplete = manifest.model_copy(
            update={
                "report_deadlines": {
                    key: value
                    for key, value in manifest.report_deadlines.items()
                    if key != extra.report_id
                }
            }
        )
        import hashlib

        incomplete_digest = hashlib.sha256(incomplete.model_dump_json().encode()).hexdigest()
        with pytest.raises(AccessDenied):
            manager.apply(
                new_epoch, incomplete, backup_at=backup_at, expected_sha256=incomplete_digest
            )

        class FailedDeletion:
            def delete(self, _key):
                raise OSError("Synthetic isolated object deletion failure")

            def inventory(self):
                return archived_store.inventory()

        broken = RecoveryManager(repo, FailedDeletion(), database_role="seva_test")
        with pytest.raises(OSError):
            broken.apply(new_epoch, manifest, backup_at=backup_at, expected_sha256=digest)
        with pytest.raises(AccessDenied):
            manager.release(new_epoch, expected_sha256=digest)
        with pytest.raises(PersistenceError):
            repo.resident_detail(OTHER, f["b"].report_id)
        started = time.perf_counter()
        manager.apply(new_epoch, manifest, backup_at=backup_at, expected_sha256=digest)
        manager.release(new_epoch, expected_sha256=digest)
        replay_seconds = time.perf_counter() - started
        with sessions() as session:
            assert session.scalar(select(func.count()).select_from(AuthSession)) == 0
            assert session.scalar(select(func.count()).select_from(AuthSessionSecret)) == 0
            assert not any(m.state == "ACTIVE" for m in session.scalars(select(Membership)))
            assert not session.get(Identity, f["users"][REVIEWER.subject]).active
            assert session.get(Report, f["a"].report_id).description is None
            assert session.get(Report, extra.report_id).description is None
            assert session.get(Media, f["media_b"]).object_key is None
            assert all(
                fragment.payload is None and fragment.content_sha256 is None
                for fragment in session.scalars(select(EvidenceFragment))
            )
            assert not any(
                j.state in {"PENDING", "RUNNING", "RETRY_WAIT"}
                for j in session.scalars(select(Job))
            )
        # Test-injected principals represent fresh sign-in; old restored sessions are gone.
        assert repo.resident_detail(OTHER, f["b"].report_id).description
        with pytest.raises(NotFound):
            repo.resident_detail(RESIDENT, f["a"].report_id)
        with pytest.raises(NotFound):
            repo.resident_detail(RESIDENT, extra.report_id)
        with pytest.raises(NotFound):
            PrivateMediaService(repo, archived_store).read(OTHER, f["media_b"])
        assert archived_store.inventory() == []
        output = os.getenv("SEVA_EVIDENCE_DIR")
        if output:
            Path(output).mkdir(parents=True, exist_ok=True)
            (Path(output) / "restore.json").write_text(
                json.dumps(
                    dict(
                        kind="synthetic_local_recovery",
                        samples=1,
                        source_reports=3,
                        archived_objects=2,
                        dump_bytes=len(archive),
                        dump_seconds=round(dump_seconds, 4),
                        restore_seconds=round(restore_seconds, 4),
                        replay_cleanup_seconds=round(replay_seconds, 4),
                        post_backup_report_deletions=1,
                        post_backup_media_deletions=1,
                        expired_reports=1,
                        provider_calls=0,
                        production_backup_tested=False,
                    ),
                    indent=2,
                )
                + "\n"
            )
    finally:
        if engine:
            engine.dispose()
        with f["engine"].connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.execute(text("DROP DATABASE seva_restore_test WITH (FORCE)"))


def test_database_restart_recovers_persisted_case_and_session(access_fixture):
    f = access_fixture
    pg = container()
    subprocess.run(["docker", "restart", pg], capture_output=True, check=True)
    for _ in range(60):
        result = subprocess.run(
            ["docker", "exec", pg, "pg_isready", "-U", "seva_test", "-d", "seva_phase1_test"],
            capture_output=True,
        )
        if result.returncode == 0:
            break
        time.sleep(0.25)
    else:
        pytest.fail("Disposable PostgreSQL did not restart within the bounded rehearsal")
    response = f["client"].get(
        f"/api/v2/resident/reports/{f['a'].report_id}", headers=f["headers"][RESIDENT.subject]
    )
    assert response.status_code == 200 and response.json()["description"]


def test_empty_bootstrap_and_repeated_initialisation_guard(pg):
    from app.operations.readiness import require_released
    from app.persistence.models import Base
    from app.resident.storage import NoMediaStore

    _url, engine, sessions = pg
    names = ",".join(f'"{name}"' for name in Base.metadata.tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {names} CASCADE"))
        connection.execute(
            text("INSERT INTO recovery_control(name,state) VALUES ('pilot','QUARANTINED')")
        )
    repo = DurableRepository(sessions)
    manager = RecoveryManager(repo, NoMediaStore(), database_role="seva_test")
    epoch = uuid4()
    manager.initialise_empty(epoch)
    with sessions() as session:
        require_released(session, epoch)
    with pytest.raises(AccessDenied):
        manager.initialise_empty(uuid4())
    with pytest.raises(AccessDenied):
        RecoveryManager(repo, NoMediaStore(), database_role="wrong-role").quarantine(uuid4())
    manager.quarantine(uuid4())
    with pytest.raises(AccessDenied):
        manager.initialise_empty(uuid4())
