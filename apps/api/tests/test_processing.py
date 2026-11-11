"""Real PostgreSQL worker recovery; synthetic providers only."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update
from test_access import access_fixture as access_fixture
from test_access import fixture as fixture
from test_access import persistence_fixture as persistence_fixture
from test_access import pg as pg
from test_access import signing_key as signing_key
from test_authority import act, detail
from test_citizen import FakeAnalyzer
from test_citizen import output as output
from test_persistence import RESIDENT, REVIEWER

from app.citizen.models import AnalysisStatus
from app.citizen.settings import CitizenSettings
from app.persistence.contracts import Conflict
from app.persistence.models import AnalysisRun, EvidenceVersion, Job, Membership, Report
from app.processing.queue import DurableQueue
from app.processing.worker import ProcessingWorker


def worker(f, output, *, status=None):
    f["repo"].clock = lambda: datetime.now(UTC)
    analyzer = FakeAnalyzer(output, failure=status)
    analyzer.settings = CitizenSettings(project="synthetic", timeout_seconds=1)
    app = f["client"].app
    return ProcessingWorker(
        f["repo"],
        app.state.environment,
        analyzer,
        app.state.corroboration_settings,
        store=f["store"],
        queue=DurableQueue(f["repo"], backoff=(0, 0)),
    )


def isolate(f):
    with f["sessions"].begin() as session:
        session.execute(
            update(Job).where(Job.report_id != f["a"].report_id).values(state="CANCELLED")
        )


def job(f):
    with f["sessions"]() as session:
        return session.scalar(
            select(Job)
            .where(Job.report_id == f["a"].report_id)
            .order_by(Job.created_at.desc(), Job.id.desc())
            .limit(1)
        )


def test_atomic_acceptance_and_concurrent_claims(access_fixture, output):
    f = access_fixture
    w = worker(f, output)
    barrier = Barrier(3)

    def claim():
        barrier.wait()
        return w.queue.claim()

    with ThreadPoolExecutor(max_workers=3) as pool:
        leases = list(pool.map(lambda _: claim(), range(3)))
    assert len([x for x in leases if x]) == 2
    assert len({x.job_id for x in leases if x}) == 2
    with f["sessions"]() as session:
        assert session.scalar(select(func.count()).select_from(Report)) == 2
        assert session.scalar(select(func.count()).select_from(Job)) == 2
        assert session.scalar(select(func.count()).select_from(AnalysisRun)) == 8


def test_lease_recovery_fencing_duplicate_and_heartbeat(access_fixture, output):
    f = access_fixture
    isolate(f)
    import time

    w = worker(f, output)
    w.queue.lease_seconds = 1
    first = w.queue.claim()
    case, snapshot = w.queue.snapshot(first)
    w.queue.heartbeat(first, case)
    assert w.queue.claim() is None
    time.sleep(1.1)  # Real database-clock visibility expiry, not a mocked clock.
    second = w.queue.claim()
    assert first.token != second.token and first.job_id == second.job_id
    with pytest.raises(Conflict):
        f["repo"].append_evidence(
            first,
            case,
            request_id=snapshot["request_id"],
            fragments=[],
            worker_states={
                s: ("FAILED", "TIMEOUT")
                for s in ("VISUAL", "ENVIRONMENT", "CORROBORATION", "FORECAST")
            },
        )
    asyncio.run(w.execute(second))
    asyncio.run(w.execute(second))
    with f["sessions"]() as session:
        assert session.scalar(select(func.count()).select_from(EvidenceVersion)) == 1
        assert session.get(Job, first.job_id).state == "PARTIAL"
    assert detail(f).json()["review_state"] == "NEW"
    from uuid import UUID

    version = UUID(detail(f).json()["evidence_versions"][0]["id"])
    prior = f["repo"].evidence(f["principals"][REVIEWER.subject], case, version)
    assert any(fragment["payload"] is not None for fragment in prior["fragments"])
    queued = act(f, "enrichments", {"reason": "Failed refresh keeps historical source content"})
    assert queued.status_code == 202
    failed = worker(f, output, status=AnalysisStatus.TIMEOUT)
    for _ in range(3):
        assert asyncio.run(failed.run_once())
    assert job(f).state == "FAILED"
    assert f["repo"].evidence(f["principals"][REVIEWER.subject], case, version) == prior


def test_retry_exhaustion_and_manual_refresh_versions(access_fixture, output):
    f = access_fixture
    isolate(f)
    w = worker(f, output, status=AnalysisStatus.TIMEOUT)
    for _ in range(3):
        assert asyncio.run(w.run_once())
    assert job(f).state == "FAILED" and job(f).attempts == 3
    assert job(f).safe_reason == "RETRY_EXHAUSTED"
    old = detail(f).json()["evidence_versions"][0]["id"]
    response = act(f, "enrichments", {"reason": "New authorised run"})
    assert response.status_code == 202 and response.json()["state"] == "PENDING"
    duplicate = act(f, "enrichments", {"reason": "Repeated click"})
    assert duplicate.json()["request_id"] == response.json()["request_id"]
    for _ in range(3):
        assert asyncio.run(w.run_once())
    versions = detail(f).json()["evidence_versions"]
    assert len(versions) == 2 and old in {v["id"] for v in versions}
    assert act(f, "internal-notes", {"body": "Review continues during failure"}).status_code == 200
    own = f["client"].get(
        f"/api/v2/resident/reports/{f['a'].report_id}", headers=f["headers"][RESIDENT.subject]
    )
    assert own.status_code == 200 and own.json()["processing"]["state"] == "FAILED"


def test_quota_precedes_provider(access_fixture, output):
    f = access_fixture
    isolate(f)
    w = worker(f, output, status=AnalysisStatus.AUTH_ERROR)
    f["repo"].limits = f["repo"].limits.model_copy(update={"provider_calls_per_day": 0})
    assert asyncio.run(w.run_once())
    assert not w.collector.analyzer.calls
    assert job(f).state == "FAILED" and job(f).safe_reason == "PILOT_QUOTA_DENIED"
    assert detail(f).status_code == 200


@pytest.mark.parametrize("operation", ["delete", "expire", "withdraw", "revoke"])
def test_inflight_late_results_never_resurrect(access_fixture, output, operation):
    f = access_fixture
    isolate(f)
    w = worker(f, output)
    with f["sessions"].begin() as session:
        session.get(Job, job(f).id).requested_by = f["users"][REVIEWER.subject]
    base = w.collector.analyzer

    class Mutating:
        settings = base.settings

        async def analyze(self, *args):
            value = await base.analyze(*args)
            if operation == "delete":
                f["repo"].delete_report(f["principals"][RESIDENT.subject], f["a"].report_id)
            else:
                with f["sessions"].begin() as session:
                    if operation == "revoke":
                        session.execute(
                            update(Membership)
                            .where(Membership.user_id == f["users"][REVIEWER.subject])
                            .values(state="REVOKED")
                        )
                    else:
                        report = session.get(Report, f["a"].report_id)
                        if operation == "expire":
                            report.content_expires_at = datetime.now(UTC) - timedelta(seconds=1)
                        else:
                            report.withdrawn_at = datetime.now(UTC)
            return value

    w.collector.analyzer = Mutating()
    asyncio.run(w.run_once())
    with f["sessions"]() as session:
        assert session.scalar(select(func.count()).select_from(EvidenceVersion)) == 0
    assert job(f).state == "CANCELLED"


def test_sigkill_mid_job_restart_recovers_accepted_case(access_fixture, output):
    import os
    import selectors
    import subprocess
    import sys
    from pathlib import Path

    f = access_fixture
    isolate(f)
    child = subprocess.Popen(
        [sys.executable, str(Path(__file__).with_name("processing_crash_fixture.py"))],
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        with selectors.DefaultSelector() as ready:
            ready.register(child.stdout, selectors.EVENT_READ)
            assert ready.select(timeout=15), "Worker did not enter synthetic collection"
            assert child.stdout.readline().strip() == b"COLLECTING"
        assert job(f).state == "RUNNING"
        assert detail(f).status_code == 200
        child.kill()
        child.wait(timeout=5)
        with f["sessions"].begin() as session:
            row = session.get(Job, job(f).id)
            row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        restarted = worker(f, output)
        assert asyncio.run(restarted.run_once())
        assert job(f).state == "PARTIAL" and job(f).attempts == 2
        with f["sessions"]() as session:
            assert session.scalar(select(func.count()).select_from(EvidenceVersion)) == 1
        assert detail(f).json()["review_state"] == "NEW"
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        child.stdout.close()


@pytest.mark.parametrize("source", ["GEMINI", "NASA_FIRMS", "SENTINEL_5P"])
def test_each_provider_failure_preserves_independent_success(access_fixture, output, source):
    from app.environment.http import ProviderFailure
    from app.environment.models import SourceState
    from app.environment.satellite import PRODUCTS, absent

    f = access_fixture
    isolate(f)
    w = worker(f, output, status=AnalysisStatus.AUTH_ERROR if source == "GEMINI" else None)

    class Fires:
        name, configured = "synthetic_fires", True

        async def fetch(self, *_args):
            if source == "NASA_FIRMS":
                raise ProviderFailure(SourceState.UNAVAILABLE, "Synthetic transient failure")
            return []  # Genuine empty synthetic observation set, not missing-provider substitution.

    class Satellite:
        name, configured = "synthetic_satellite", True

        async def fetch(self, _query):
            reason = "timeout" if source == "SENTINEL_5P" else "no_scene"
            return [
                absent(p, SourceState.UNAVAILABLE, reason, "Synthetic source outcome")
                for p in PRODUCTS
            ]

    w.collector.environment.providers["fires"] = Fires()
    w.collector.environment.satellite = Satellite()
    assert asyncio.run(w.run_once())
    assert job(f).state == "PARTIAL" and job(f).attempts == 1
    version_id = detail(f).json()["evidence_versions"][0]["id"]
    from uuid import UUID

    read = f["repo"].evidence(f["principals"][REVIEWER.subject], f["a"].case_id, UUID(version_id))
    failed = next(x for x in read["fragments"] if x["source"] == source)
    assert failed["payload"] is None and failed["state"] == "UNAVAILABLE"
    assert any(x["payload"] is not None for x in read["fragments"])
    assert detail(f).json()["review_state"] == "NEW"


def test_expired_objects_jobs_metrics_and_restore_guards(access_fixture, output):
    from app.persistence.models import Media, ProcessingMetric
    from app.persistence.retention import RetentionService

    f = access_fixture
    isolate(f)
    w = worker(f, output)
    assert asyncio.run(w.run_once())
    with f["sessions"].begin() as session:
        row = session.get(Report, f["a"].report_id)
        row.content_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.execute(
            update(ProcessingMetric).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        # Simulate an old pending queue entry restored with already expired report/media.
        session.get(Job, job(f).id).state = "PENDING"
    assert asyncio.run(w.run_once())
    assert job(f).state == "CANCELLED"
    RetentionService(f["repo"], f["store"]).sweep()
    with f["sessions"]() as session:
        assert session.get(Report, f["a"].report_id).description is None
        assert session.get(Media, f["media_a"]).object_key is None
        assert session.scalar(select(func.count()).select_from(ProcessingMetric)) == 0
    assert not f["store"].inventory() or len(f["store"].inventory()) == 1  # unit B remains private


def test_worker_restricted_database_role_can_publish_without_session_secrets(
    access_fixture, output
):
    from pathlib import Path

    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError
    from sqlalchemy.orm import sessionmaker

    f = access_fixture
    isolate(f)
    from app.operations.readiness import pulse
    from app.persistence.models import RecoveryControl

    f["repo"].release_epoch = uuid4()
    with f["sessions"].begin() as session:
        row = session.get(RecoveryControl, "pilot")
        row.epoch, row.state = f["repo"].release_epoch, "READY"
    role = "synthetic_processing_worker"
    grants = (
        (Path(__file__).resolve().parents[1] / "scripts/worker_roles.sql")
        .read_text()
        .replace(':"worker_role"', role)
    )
    with f["engine"].begin() as connection:
        connection.execute(text(f"CREATE ROLE {role} NOLOGIN"))
        connection.exec_driver_sql(grants)
    try:
        with f["engine"].connect() as connection:
            connection.execute(text(f"SET ROLE {role}"))
            connection.commit()
            original = f["repo"].sessions
            f["repo"].sessions = sessionmaker(connection, expire_on_commit=False)
            try:
                pulse(f["repo"], "processing")
                w = worker(f, output)
                assert asyncio.run(w.run_once())
                with pytest.raises(ProgrammingError):
                    connection.execute(text("SELECT * FROM auth_session_secrets"))
                connection.rollback()
                for sql in (
                    "UPDATE unit_memberships SET state='ACTIVE' WHERE false",
                    "UPDATE reports SET deletion_state='ACTIVE' WHERE false",
                    "UPDATE users SET active=true WHERE false",
                    "UPDATE recovery_control SET state='READY' WHERE false",
                    "UPDATE maintenance_heartbeats SET succeeded_at=now() WHERE false",
                ):
                    with pytest.raises(ProgrammingError):
                        connection.execute(text(sql))
                    connection.rollback()
            finally:
                f["repo"].sessions = original
                connection.execute(text("RESET ROLE"))
                connection.commit()
        assert job(f).state == "PARTIAL"
    finally:
        with f["engine"].begin() as connection:
            connection.execute(text(f"DROP OWNED BY {role}"))
            connection.execute(text(f"DROP ROLE {role}"))


def test_concurrent_workers_share_paid_quota(access_fixture, output):
    f = access_fixture
    f["repo"].limits = f["repo"].limits.model_copy(update={"provider_calls_per_day": 1})
    workers = [worker(f, output), worker(f, output)]
    barrier = Barrier(2)

    def consume(w):
        barrier.wait()
        return asyncio.run(w.run_once())

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert all(pool.map(consume, workers))
    assert sum(len(w.collector.analyzer.calls) for w in workers) == 1
    with f["sessions"]() as session:
        assert set(session.scalars(select(Job.state))) == {"PARTIAL", "FAILED"}


def test_permanent_configuration_is_not_retried_and_logs_are_minimised(
    access_fixture, output, caplog
):
    import logging

    from app.persistence.models import ProcessingMetric

    f = access_fixture
    isolate(f)
    caplog.set_level(logging.INFO)
    w = worker(f, output, status=AnalysisStatus.AUTH_ERROR)
    assert asyncio.run(w.run_once())
    assert job(f).state == "FAILED" and job(f).attempts == 1
    assert not asyncio.run(w.run_once())
    detail(f)
    with f["sessions"]() as session:
        metrics = list(session.scalars(select(ProcessingMetric)))
        assert metrics and all(m.duration_ms >= 0 for m in metrics)
        assert sum(m.usage_units for m in metrics) == 1
    protected = [r.message for r in caplog.records if "protected_request" in r.message]
    assert protected and all("duration_ms" in line for line in protected)
    assert all(str(f["a"].case_id) not in line and "28.5" not in line for line in protected)
