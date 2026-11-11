"""Synthetic real PostgreSQL 18 proof; deliberately never connects to a hosted database.

Without TEST_DATABASE_URL these tests skip, never silently substitute SQLite. CI supplies
a disposable service. This suite destroys ONLY the explicitly named local test schema.
"""

import io
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier, Event
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import event, func, inspect, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app.main import create_app
from app.persistence.contracts import (
    AccessDenied,
    Conflict,
    FirmsPayload,
    FragmentInput,
    Gone,
    NotFound,
    PersistenceError,
    Principal,
    ReportSubmission,
    SentinelPayload,
)
from app.persistence.database import SCHEMA_REVISION, database
from app.persistence.media import LocalPrivateMediaStore, PrivateMediaService
from app.persistence.models import (
    AnalysisRun,
    Base,
    Case,
    EvidenceFragment,
    EvidenceRedaction,
    EvidenceVersion,
    IdempotencyKey,
    Identity,
    InternalNote,
    Job,
    Media,
    Membership,
    PrivacyRequest,
    Report,
    ReporterUpdate,
    ReviewEvent,
    Unit,
    VerificationTask,
)
from app.persistence.repository import DurableRepository
from app.persistence.retention import RetentionService

API_ROOT = Path(__file__).resolve().parents[1]
ISSUER = "https://synthetic-issuer.invalid/"
RESIDENT = Principal(ISSUER, "resident-a")
OTHER = Principal(ISSUER, "resident-b")
REVIEWER = Principal(ISSUER, "reviewer-a")
OUTSIDER = Principal(ISSUER, "reviewer-b")


@pytest.fixture(scope="module")
def pg():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Real PostgreSQL proof requires explicit TEST_DATABASE_URL; no SQLite fallback")
    parsed = make_url(url)
    if (
        parsed.host not in {"127.0.0.1", "localhost"}
        or parsed.database != "seva_phase1_test"
        or parsed.username != "seva_test"
    ):
        pytest.fail("Refusing to mutate anything except the named local synthetic test database")
    old = os.environ.get("SEVA_MIGRATION_DATABASE_URL")
    os.environ["SEVA_MIGRATION_DATABASE_URL"] = url
    config = Config(str(API_ROOT / "alembic.ini"))
    try:
        # This is the explicitly guarded disposable DB. Clear fixture records before
        # structural rollback: v4 manual request/source kinds cannot be represented by v3.
        cleanup_engine, _ = database(url)
        with cleanup_engine.begin() as connection:
            tables = [
                name for name in inspect(connection).get_table_names() if name != "alembic_version"
            ]
            if tables:
                quoted = ",".join(
                    connection.dialect.identifier_preparer.quote(name) for name in tables
                )
                connection.execute(text(f"TRUNCATE {quoted} CASCADE"))
        cleanup_engine.dispose()
        # Exercise downgrade/reapply as well as a genuinely empty schema migration.
        command.downgrade(config, "base")
        engine, sessions = database(url)
        with engine.connect() as conn:
            assert set(inspect(conn).get_table_names()) <= {"alembic_version"}
        command.upgrade(config, "head")
        command.check(config)
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT version_num FROM alembic_version")) == SCHEMA_REVISION
            assert int(conn.scalar(text("SHOW server_version_num"))) >= 180000
            assert set(Base.metadata.tables) <= set(inspect(conn).get_table_names())
            assert any(
                f["name"] == "fk_cases_latest_evidence"
                for f in inspect(conn).get_foreign_keys("cases")
            )
        yield url, engine, sessions
        engine.dispose()
    finally:
        if old is None:
            os.environ.pop("SEVA_MIGRATION_DATABASE_URL", None)
        else:
            os.environ["SEVA_MIGRATION_DATABASE_URL"] = old


@pytest.fixture
def fixture(pg, tmp_path):
    url, engine, sessions = pg
    names = ",".join(f'"{t}"' for t in Base.metadata.tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {names} CASCADE"))
        conn.execute(
            text("INSERT INTO recovery_control(name,state) VALUES ('pilot','QUARANTINED')")
        )
    now = datetime.now(UTC)
    unit_id, other_unit = uuid4(), uuid4()
    users = {}
    with sessions.begin() as session:
        for subject in (RESIDENT.subject, OTHER.subject, REVIEWER.subject, OUTSIDER.subject):
            user = Identity(issuer=ISSUER, subject=subject, created_at=now)
            session.add(user)
            session.flush()
            users[subject] = user.id
        session.add_all(
            [
                Unit(id=unit_id, name="Synthetic triage", approved_at=now),
                Unit(id=other_unit, name="Synthetic other unit", approved_at=now),
            ]
        )
        session.flush()
        for principal, unit in ((REVIEWER, unit_id), (OUTSIDER, other_unit)):
            session.add(
                Membership(
                    user_id=users[principal.subject],
                    unit_id=unit,
                    role="REVIEWER",
                    state="ACTIVE",
                    approved_by=users[OTHER.subject],
                    approved_at=now,
                )
            )
    clock = [now]
    repo = DurableRepository(
        sessions, triage_unit_id=unit_id, clock=lambda: clock[0], provider_retention_reviewed=True
    )  # Synthetic source fixtures ONLY.
    store = LocalPrivateMediaStore((tmp_path / "private").resolve())
    return {
        "url": url,
        "engine": engine,
        "sessions": sessions,
        "repo": repo,
        "store": store,
        "media": PrivateMediaService(repo, store),
        "unit": unit_id,
        "users": users,
        "clock": clock,
    }


def submission(**kwargs):
    return ReportSubmission(
        description="Synthetic smoke report",
        declared_category="UNSURE",
        reported_latitude=28.5,
        reported_longitude=77.1,
        **kwargs,
    )


def accept(fixture, *, data=None, key=None, principal=RESIDENT, created=None):
    return fixture["repo"].create_report(
        principal,
        data or submission(),
        key=key or uuid4(),
        key_created_at=created or fixture["clock"][0],
    )


def image_bytes():
    output = io.BytesIO()
    image = Image.new("RGB", (32, 24), "gray")
    exif = Image.Exif()
    exif[0x010E] = "Synthetic private metadata that must disappear"
    image.save(output, format="JPEG", exif=exif)
    return output.getvalue()


def initial_request(fixture, report_id):
    with fixture["sessions"]() as session:
        return session.scalar(select(Job.request_id).where(Job.report_id == report_id))


def evidence(fixture, receipt, request=None):
    return fixture["repo"].append_evidence(
        REVIEWER,
        receipt.case_id,
        request_id=request or initial_request(fixture, receipt.report_id),
        fragments=[
            FragmentInput(
                payload=FirmsPayload(dataset="VIIRS_NOAA20_NRT", detection_count=0),
                retrieved_at=fixture["clock"][0],
            )
        ],
    )


def test_clean_migration_constraints_and_text_acceptance(fixture):
    result = accept(fixture)
    with fixture["sessions"]() as session:
        report = session.get(Report, result.report_id)
        case = session.get(Case, result.case_id)
        assert case.report_id == report.id and case.revision == 0
        assert report.declared_capture_at is None and report.capture_time_basis == "unknown"
        assert session.scalar(select(func.count()).select_from(ReporterUpdate)) == 1
        assert session.scalar(select(Job.state)) == "PENDING"
        visual = session.scalar(select(AnalysisRun).where(AnalysisRun.stage == "VISUAL"))
        assert (visual.state, visual.safe_reason) == ("NOT_APPLICABLE", "NO_IMAGE")
        assert session.scalar(select(func.count()).select_from(EvidenceVersion)) == 0
    assert fixture["repo"].resident_detail(RESIDENT, result.report_id).reporter_status == "RECEIVED"
    with pytest.raises(IntegrityError), fixture["sessions"].begin() as session:
        session.add(Case(report_id=result.report_id, created_at=fixture["clock"][0]))


def test_idempotency_replay_mismatch_and_scoping(fixture):
    key, now = uuid4(), fixture["clock"][0]
    original = accept(fixture, key=key)
    fixture["clock"][0] += timedelta(days=2)
    replay = accept(fixture, key=key, created=now)
    assert replay.replayed and replay.report_id == original.report_id
    assert replay.case_id == original.case_id and replay.receipt_id == original.receipt_id
    changed = submission().model_copy(update={"description": "Different synthetic payload"})
    with pytest.raises(Conflict):
        accept(fixture, key=key, created=now, data=changed)
    with pytest.raises(Conflict):
        accept(fixture, key=key)  # The stable creation header is part of the retry envelope.
    another = accept(fixture, key=key, principal=OTHER)
    assert another.report_id != original.report_id
    with pytest.raises(Gone):
        accept(fixture, created=now)
    with pytest.raises(ValueError):
        accept(fixture, created=fixture["clock"][0] + timedelta(seconds=61))
    with fixture["sessions"]() as session:
        assert session.scalar(select(func.count()).select_from(Report)) == 2


def test_concurrent_duplicate_acceptance_one_report_case_job(fixture):
    barrier, key = Barrier(2), uuid4()

    def create():
        barrier.wait(timeout=10)
        return accept(fixture, key=key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create(), range(2)))
    assert len({r.report_id for r in results}) == 1
    assert sorted(r.replayed for r in results) == [False, True]
    with fixture["sessions"]() as session:
        for model in (Report, Case, Job, IdempotencyKey, ReporterUpdate):
            assert session.scalar(select(func.count()).select_from(model)) == 1


def test_acceptance_rollback_never_returns_receipt_or_half_case(fixture):
    def reject_job(_mapper, _connection, _target):
        raise RuntimeError("Synthetic commit failure")

    event.listen(Job, "before_insert", reject_job)
    try:
        with pytest.raises(RuntimeError):
            accept(fixture)
    finally:
        event.remove(Job, "before_insert", reject_job)
    with fixture["sessions"]() as session:
        for model in (Report, Case, Job, IdempotencyKey, ReporterUpdate, AnalysisRun):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_actual_api_process_loss_restart_and_second_instance(fixture):
    # Abrupt exit from a live API lifespan AFTER commit; no in-memory repository survives.
    program = """
import json, os
from datetime import UTC, datetime
from uuid import UUID, uuid4
from fastapi.testclient import TestClient
from app.main import create_app
from app.persistence.contracts import Principal, ReportSubmission
from app.persistence.database import database
from app.persistence.repository import DurableRepository
engine, sessions = database(os.environ["TEST_DATABASE_URL"])
repo = DurableRepository(sessions, triage_unit_id=UUID(os.environ["UNIT"]))
api = create_app(persistence=repo)
resident = Principal("https://synthetic-issuer.invalid/", "resident-a")
reviewer = Principal("https://synthetic-issuer.invalid/", "reviewer-a")
with TestClient(api):
    if os.environ["ACTION"] == "write":
        result = api.state.persistence.create_report(resident, ReportSubmission(
            description="Synthetic restart proof", declared_category="DUST",
            reported_latitude=28.5, reported_longitude=77.1),
            key=uuid4(), key_created_at=datetime.now(UTC))
        api.state.persistence.review(reviewer, result.case_id,
            expected_revision=0, state="UNDER_REVIEW")
        payload = {"receipt": result.model_dump(mode="json"), "pid": os.getpid()}
        print(json.dumps(payload), flush=True)
        os._exit(0)
    else:
        report_id, case_id = UUID(os.environ["REPORT"]), UUID(os.environ["CASE"])
        detail = api.state.persistence.resident_detail(resident, report_id)
        history = api.state.persistence.authority_detail(reviewer, case_id).history
        print(json.dumps({"detail": detail.model_dump(mode="json"), "history": history,
            "pid": os.getpid()}), flush=True)
engine.dispose()
"""
    env = {
        "PATH": os.environ["PATH"],
        "TEST_DATABASE_URL": fixture["url"],
        "UNIT": str(fixture["unit"]),
        "ACTION": "write",
    }
    written = json.loads(
        subprocess.check_output(
            [sys.executable, "-c", program], cwd=API_ROOT, env=env, timeout=30, text=True
        )
    )
    receipt = written["receipt"]
    env |= {"ACTION": "read", "REPORT": receipt["report_id"], "CASE": receipt["case_id"]}
    read = json.loads(
        subprocess.check_output(
            [sys.executable, "-c", program], cwd=API_ROOT, env=env, timeout=30, text=True
        )
    )
    assert read["pid"] != written["pid"]
    assert read["detail"]["id"] == receipt["report_id"]
    assert read["detail"]["description"] == "Synthetic restart proof"
    assert read["history"] == [
        {"revision": 1, "action": "REVIEW_UNDER_REVIEW", "evidence_version_id": None}
    ]
    engine2, sessions2 = database(fixture["url"])
    try:
        api2 = create_app(persistence=DurableRepository(sessions2))
        with TestClient(api2):
            assert (
                api2.state.persistence.authority_detail(REVIEWER, UUID(receipt["case_id"])).history
                == read["history"]
            )
    finally:
        engine2.dispose()


def test_concurrent_revision_one_winner_and_atomic_history(fixture):
    receipt, barrier = accept(fixture), Barrier(2)

    def review():
        barrier.wait(timeout=10)
        try:
            return fixture["repo"].review(
                REVIEWER, receipt.case_id, expected_revision=0, state="UNDER_REVIEW"
            )
        except Conflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: review(), range(2)))
    assert sorted(results, key=str) == [1, "conflict"]
    with fixture["sessions"]() as session:
        assert session.get(Case, receipt.case_id).revision == 1
        assert session.scalar(select(func.count()).select_from(ReviewEvent)) == 1


def test_review_rollback_preserves_revision_and_event_count(fixture):
    receipt = accept(fixture)

    def reject_event(*_args):
        raise RuntimeError("Synthetic audit insert failure")

    event.listen(ReviewEvent, "before_insert", reject_event)
    try:
        with pytest.raises(RuntimeError):
            fixture["repo"].review(
                REVIEWER, receipt.case_id, expected_revision=0, state="UNDER_REVIEW"
            )
    finally:
        event.remove(ReviewEvent, "before_insert", reject_event)
    with fixture["sessions"]() as session:
        assert session.get(Case, receipt.case_id).revision == 0
        assert session.scalar(select(func.count()).select_from(ReviewEvent)) == 0


def test_evidence_frozen_refresh_append_and_database_guards(fixture):
    receipt = accept(fixture)
    version1 = evidence(fixture, receipt)
    before = fixture["repo"].evidence(REVIEWER, receipt.case_id, version1)
    with fixture["sessions"]() as session:
        frozen = session.scalar(text("SELECT row_to_json(v)::text FROM evidence_versions v"))
        frozen_fragments = (
            session.execute(
                text("SELECT row_to_json(f)::text FROM evidence_fragments f ORDER BY source")
            )
            .scalars()
            .all()
        )
    with pytest.raises(Conflict):
        fixture["repo"].review(REVIEWER, receipt.case_id, expected_revision=0, state="UNDER_REVIEW")
    fixture["repo"].review(REVIEWER, receipt.case_id, expected_revision=1, state="UNDER_REVIEW")
    with fixture["sessions"]() as session:
        assert (
            session.scalar(text("SELECT row_to_json(v)::text FROM evidence_versions v")) == frozen
        )
        assert (
            session.execute(
                text("SELECT row_to_json(f)::text FROM evidence_fragments f ORDER BY source")
            )
            .scalars()
            .all()
            == frozen_fragments
        )
    assert fixture["repo"].evidence(REVIEWER, receipt.case_id, version1) == before
    request2 = fixture["repo"].request_refresh(REVIEWER, receipt.case_id, expected_revision=2)
    version2 = evidence(fixture, receipt, request2)
    assert version1 != version2
    assert fixture["repo"].evidence(REVIEWER, receipt.case_id, version2)["version"] == 2
    assert fixture["repo"].evidence(REVIEWER, receipt.case_id, version1) == before
    with pytest.raises(IntegrityError), fixture["sessions"].begin() as session:
        session.execute(
            update(EvidenceVersion)
            .where(EvidenceVersion.id == version1)
            .values(input_policy="silently_replaced")
        )
    with pytest.raises(IntegrityError), fixture["sessions"].begin() as session:
        session.execute(
            update(EvidenceFragment)
            .where(EvidenceFragment.source == "NASA_FIRMS")
            .values(payload={"changed": True})
        )
    with pytest.raises(IntegrityError), fixture["sessions"].begin() as session:
        session.execute(update(ReviewEvent).values(action="REWRITTEN"))
    with pytest.raises(Conflict):
        evidence(fixture, receipt)


def test_source_expiry_hides_then_physically_purges_payload_and_hash(fixture):
    receipt = accept(fixture)
    version = evidence(fixture, receipt)
    fixture["clock"][0] += timedelta(days=31)
    read = fixture["repo"].evidence(REVIEWER, receipt.case_id, version)
    firms = next(f for f in read["fragments"] if f["source"] == "NASA_FIRMS")
    assert firms["payload"] is None and firms["state"] == "EXPIRED_BY_SOURCE_POLICY"
    RetentionService(fixture["repo"], fixture["store"]).sweep()
    with fixture["sessions"]() as session:
        assert session.get(EvidenceVersion, version).input_fingerprint is None
        fragment = session.scalar(
            select(EvidenceFragment).where(EvidenceFragment.source == "NASA_FIRMS")
        )
        assert fragment.payload is None and fragment.content_sha256 is None
        assert session.scalar(select(func.count()).select_from(EvidenceRedaction)) == 1
    RetentionService(fixture["repo"], fixture["store"]).sweep()
    with fixture["sessions"]() as session:
        assert session.scalar(select(func.count()).select_from(EvidenceRedaction)) == 1


def test_private_media_metadata_stripping_scope_and_no_public_route(fixture):
    media_id = fixture["media"].stage(RESIDENT, image_bytes(), "image/jpeg")
    clean = fixture["media"].read(RESIDENT, media_id)
    assert b"Synthetic private metadata" not in clean
    with Image.open(io.BytesIO(clean)) as image:
        assert not image.getexif() and image.format == "JPEG"
    with pytest.raises(NotFound):
        fixture["media"].read(OTHER, media_id)
    with pytest.raises(NotFound):
        accept(fixture, data=submission(media_id=media_id), principal=OTHER)
    receipt = accept(fixture, data=submission(media_id=media_id))
    assert fixture["media"].read(REVIEWER, media_id, case_id=receipt.case_id) == clean
    with pytest.raises(NotFound):
        fixture["media"].read(OUTSIDER, media_id, case_id=receipt.case_id)
    with pytest.raises(NotFound):
        accept(fixture, data=submission(media_id=media_id))  # A stage can be consumed only once.
    with TestClient(create_app(persistence=fixture["repo"])) as client:
        # Phase 2 registers verified-access routes; a persistence-only injection still
        # provides no HTTP identity bypass and cannot expose these records.
        assert client.get(f"/api/v2/resident/reports/{receipt.report_id}").status_code == 401
        assert client.get(f"/api/v2/resident/media/{media_id}").status_code == 401
        assert client.get(f"/media/{media_id}").status_code == 404
        assert (
            client.get(
                "/api/v2/resident/reports",
                headers={"Authorization": "Bearer arbitrary", "X-AirshedOS-Session": "0" * 64},
            ).status_code
            == 503
        )  # No verifier/session service was injected.
    fixture["clock"][0] += timedelta(days=31)
    with pytest.raises(NotFound):
        fixture["media"].read(RESIDENT, media_id)
    RetentionService(fixture["repo"], fixture["store"]).sweep()
    assert not fixture["store"].inventory()


def test_failed_media_write_and_database_commit_recover_without_orphans(fixture, monkeypatch):
    store, media = fixture["store"], fixture["media"]
    real_put = store.put_derivative

    def fail_write(key, data):
        real_put(key, data)
        raise OSError("Synthetic write failure after bytes")

    with monkeypatch.context() as scoped:
        scoped.setattr(store, "put_derivative", fail_write)
        with pytest.raises(PersistenceError):
            media.stage(RESIDENT, image_bytes(), "image/jpeg")
    assert not store.inventory()

    def fail_ready(_mapper, _connection, target):
        if target.state == "READY":
            raise RuntimeError("Synthetic database commit failure")

    event.listen(Media, "before_update", fail_ready)
    try:
        with pytest.raises(PersistenceError):
            media.stage(RESIDENT, image_bytes(), "image/jpeg")
    finally:
        event.remove(Media, "before_update", fail_ready)
    assert not store.inventory()
    RetentionService(fixture["repo"], store).sweep()
    with fixture["sessions"]() as session:
        assert set(session.scalars(select(Media.state))) == {"DELETED"}


def test_failed_compensation_and_crash_orphan_reconciliation(fixture, monkeypatch):
    store, real_put = fixture["store"], fixture["store"].put_derivative

    def fail_put(key, data):
        real_put(key, data)
        raise OSError("Synthetic crash")

    def fail_delete(_key):
        raise OSError("Synthetic object store outage")

    with monkeypatch.context() as scoped:
        scoped.setattr(store, "put_derivative", fail_put)
        scoped.setattr(store, "delete", fail_delete)
        with pytest.raises(PersistenceError):
            fixture["media"].stage(RESIDENT, image_bytes(), "image/jpeg")
        with pytest.raises(OSError):
            RetentionService(fixture["repo"], store).sweep()
    assert len(store.inventory()) == 1
    with fixture["sessions"]() as session:
        media_id = session.scalar(select(Media.id))
    with pytest.raises(NotFound):
        fixture["media"].read(RESIDENT, media_id)
    RetentionService(fixture["repo"], store).sweep()
    assert not store.inventory()
    orphan = uuid4().hex
    store.put_derivative(orphan, b"synthetic derivative leftover")
    old = (fixture["clock"][0] - timedelta(hours=2)).timestamp()
    os.utime(store.root / orphan, (old, old))
    assert RetentionService(fixture["repo"], store).sweep()["orphans"] == 1
    assert not store.inventory()


def test_actual_commit_failure_compensates_staged_object(fixture):
    commits = []

    def fail_second_commit(_connection):
        commits.append(True)
        if len(commits) == 2:
            raise RuntimeError("Synthetic database COMMIT failure after ready-row flush")

    event.listen(fixture["engine"], "commit", fail_second_commit)
    try:
        with pytest.raises(PersistenceError):
            fixture["media"].stage(RESIDENT, image_bytes(), "image/jpeg")
    finally:
        event.remove(fixture["engine"], "commit", fail_second_commit)
    assert len(commits) >= 2
    assert not fixture["store"].inventory()
    RetentionService(fixture["repo"], fixture["store"]).sweep()
    with fixture["sessions"]() as session:
        assert session.scalar(select(Media.state)) == "DELETED"


def test_failed_acceptance_keeps_stage_owned_and_cleanup_bounded(fixture):
    media_id = fixture["media"].stage(RESIDENT, image_bytes(), "image/jpeg")

    def fail_job(*_args):
        raise RuntimeError("Synthetic acceptance failure")

    event.listen(Job, "before_insert", fail_job)
    try:
        with pytest.raises(RuntimeError):
            accept(fixture, data=submission(media_id=media_id))
    finally:
        event.remove(Job, "before_insert", fail_job)
    with fixture["sessions"]() as session:
        media = session.get(Media, media_id)
        assert media.state == "READY" and media.report_id is None
        assert session.scalar(select(func.count()).select_from(Report)) == 0
    fixture["clock"][0] += timedelta(hours=1, seconds=1)
    RetentionService(fixture["repo"], fixture["store"]).sweep()
    assert not fixture["store"].inventory()


def test_media_expiring_while_acceptance_waits_on_row_lock_cannot_be_attached(fixture):
    media_id = fixture["media"].stage(RESIDENT, image_bytes(), "image/jpeg")
    waiting = Event()
    held = fixture["sessions"]()
    held.execute(select(Media).where(Media.id == media_id).with_for_update())

    def before_query(_conn, _cursor, statement, _parameters, _context, _many):
        if "FROM media" in statement and "FOR UPDATE" in statement:
            waiting.set()

    event.listen(fixture["engine"], "before_cursor_execute", before_query)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(accept, fixture, data=submission(media_id=media_id))
            try:
                assert waiting.wait(timeout=10)
                fixture["clock"][0] += timedelta(hours=2)
            finally:
                held.rollback()
            with pytest.raises(NotFound):
                future.result(timeout=10)
    finally:
        held.close()
        event.remove(fixture["engine"], "before_cursor_execute", before_query)
    with fixture["sessions"]() as session:
        assert session.scalar(select(func.count()).select_from(Report)) == 0
    RetentionService(fixture["repo"], fixture["store"]).sweep()
    assert not fixture["store"].inventory()


def test_deletion_failed_object_purge_remains_suppressed_and_retryable(fixture, monkeypatch):
    media_id = fixture["media"].stage(RESIDENT, image_bytes(), "image/jpeg")
    receipt = accept(fixture, data=submission(media_id=media_id))
    fixture["repo"].delete_report(RESIDENT, receipt.report_id)

    def fail_delete(_key):
        raise OSError("Synthetic object deletion outage")

    with monkeypatch.context() as scoped:
        scoped.setattr(fixture["store"], "delete", fail_delete)
        with pytest.raises(OSError):
            RetentionService(fixture["repo"], fixture["store"]).sweep()
    with fixture["sessions"]() as session:
        assert session.get(Report, receipt.report_id).deletion_state == "SUPPRESSED"
        assert session.scalar(select(PrivacyRequest.purged_at)) is None
        assert session.get(Media, media_id).object_key is not None
    with pytest.raises(NotFound):
        fixture["media"].read(RESIDENT, media_id)
    RetentionService(fixture["repo"], fixture["store"]).sweep()
    assert not fixture["store"].inventory()
    with fixture["sessions"]() as session:
        assert session.scalar(select(PrivacyRequest.purged_at)) is not None


def test_later_source_expiry_is_purged_after_earliest_version_hash_is_gone(fixture):
    receipt = accept(fixture)
    now = fixture["clock"][0]
    version = fixture["repo"].append_evidence(
        REVIEWER,
        receipt.case_id,
        request_id=initial_request(fixture, receipt.report_id),
        fragments=[
            FragmentInput(
                payload=FirmsPayload(dataset="VIIRS_NOAA20_NRT", detection_count=0),
                retrieved_at=now - timedelta(days=20),
            ),
            FragmentInput(
                payload=SentinelPayload(
                    product="COPERNICUS/S5P/NRTI/L3_NO2", column_mol_m2=0.0001, valid_pixel_count=7
                ),
                retrieved_at=now,
            ),
        ],
    )
    fixture["clock"][0] += timedelta(days=11)
    RetentionService(fixture["repo"], fixture["store"]).sweep()
    with fixture["sessions"]() as session:
        assert session.get(EvidenceVersion, version).input_fingerprint is None
        assert (
            session.scalar(
                select(EvidenceFragment.payload).where(EvidenceFragment.source == "SENTINEL_5P")
            )
            is not None
        )
    fixture["clock"][0] += timedelta(days=20)
    RetentionService(fixture["repo"], fixture["store"]).sweep()
    with fixture["sessions"]() as session:
        assert (
            session.scalar(
                select(EvidenceFragment.payload).where(EvidenceFragment.source == "SENTINEL_5P")
            )
            is None
        )
        assert session.scalar(select(func.count()).select_from(EvidenceRedaction)) == 2


def test_unfinished_intent_survives_process_loss_and_expires(fixture):
    now, key = fixture["clock"][0], uuid4().hex
    with fixture["sessions"].begin() as session:
        record = Media(
            owner_id=fixture["users"][RESIDENT.subject],
            object_key=key,
            state="WRITING",
            created_at=now,
            expires_at=now + timedelta(hours=1),
        )
        session.add(record)
        session.flush()
        media_id = record.id
    fixture["store"].put_derivative(key, b"synthetic incomplete stage")
    with pytest.raises(NotFound):
        fixture["media"].read(RESIDENT, media_id)
    fixture["clock"][0] += timedelta(hours=1, seconds=1)
    RetentionService(fixture["repo"], fixture["store"]).sweep()
    assert not fixture["store"].inventory()


def test_deletion_suppression_purge_tombstone_and_later_retry_rejection(fixture):
    key, now = uuid4(), fixture["clock"][0]
    media_id = fixture["media"].stage(RESIDENT, image_bytes(), "image/jpeg")
    data = submission(media_id=media_id)
    receipt = accept(fixture, key=key, data=data)
    version = evidence(fixture, receipt)
    with pytest.raises(ValueError):
        fixture["repo"].request_verification(
            REVIEWER, receipt.case_id, expected_revision=1, instructions="x" + " " * 2000
        )
    fixture["repo"].add_internal_note(
        REVIEWER, receipt.case_id, expected_revision=1, body="Private synthetic note"
    )
    fixture["repo"].request_verification(
        REVIEWER, receipt.case_id, expected_revision=2, instructions="Synthetic field request"
    )
    fixture["repo"].delete_report(RESIDENT, receipt.report_id)
    for read in (
        lambda: fixture["repo"].resident_detail(RESIDENT, receipt.report_id),
        lambda: fixture["repo"].authority_detail(REVIEWER, receipt.case_id),
        lambda: fixture["repo"].evidence(REVIEWER, receipt.case_id, version),
        lambda: fixture["media"].read(RESIDENT, media_id),
    ):
        with pytest.raises(NotFound):
            read()
    with pytest.raises(Gone):
        accept(fixture, key=key, data=data, created=now)
    RetentionService(fixture["repo"], fixture["store"]).sweep()
    assert not fixture["store"].inventory()
    with fixture["sessions"]() as session:
        report = session.get(Report, receipt.report_id)
        assert report.description is report.reported_latitude is report.reported_longitude is None
        assert report.declared_category is report.declared_capture_at is None
        assert report.purged_at and report.deletion_state == "PURGED"
        assert session.scalar(select(InternalNote.body)) is None
        assert session.scalar(select(VerificationTask.instructions)) is None
        assert session.scalar(select(VerificationTask.state)) == "CANCELLED"
        assert session.scalar(select(IdempotencyKey.tombstone)) is True
        assert session.scalar(select(IdempotencyKey.fingerprint)) is None
        assert session.scalar(select(PrivacyRequest.purged_at)) is not None
        assert session.scalar(select(EvidenceVersion.input_fingerprint)) is None
        assert all(
            f.payload is None and f.content_sha256 is None
            for f in session.scalars(select(EvidenceFragment))
        )
    fixture["clock"][0] += timedelta(days=181)
    RetentionService(fixture["repo"], fixture["store"]).sweep()
    with fixture["sessions"]() as session:
        assert session.scalar(select(func.count()).select_from(Report)) == 0
        assert session.scalar(select(func.count()).select_from(IdempotencyKey)) == 0
    with pytest.raises(Gone):
        accept(fixture, key=key, data=data, created=now)


def test_report_expiry_read_guard_and_physical_purge(fixture):
    receipt = accept(fixture)
    fixture["clock"][0] += timedelta(days=91)
    with pytest.raises(NotFound):
        fixture["repo"].resident_detail(RESIDENT, receipt.report_id)
    RetentionService(fixture["repo"], fixture["store"]).sweep()
    with fixture["sessions"]() as session:
        assert session.get(Report, receipt.report_id).description is None
        assert session.scalar(select(IdempotencyKey.fingerprint)) is None
        assert session.scalar(select(Job.state)) == "CANCELLED"


def test_scope_isolation_revocation_and_separate_resident_projection(fixture):
    receipt = accept(fixture)
    fixture["repo"].add_internal_note(
        REVIEWER, receipt.case_id, expected_revision=0, body="Private synthetic note"
    )
    detail = fixture["repo"].resident_detail(RESIDENT, receipt.report_id).model_dump(mode="json")
    assert "Private synthetic note" not in json.dumps(detail)
    assert set(detail) == {
        "reported_place",
        "information_requests",
        "supplements",
        "id",
        "receipt_id",
        "accepted_at",
        "content_expires_at",
        "description",
        "declared_category",
        "reported_location",
        "declared_capture_at",
        "capture_time_basis",
        "media",
        "reporter_status",
        "published_updates",
        "processing",
        "withdrawn_at",
        "deletion_state",
    }
    with pytest.raises(NotFound):
        fixture["repo"].resident_detail(OTHER, receipt.report_id)
    for principal in (RESIDENT, OUTSIDER):
        with pytest.raises(NotFound):
            fixture["repo"].authority_detail(principal, receipt.case_id)
        with pytest.raises(NotFound):
            fixture["repo"].review(
                principal, receipt.case_id, expected_revision=1, state="UNDER_REVIEW"
            )
    with pytest.raises(AccessDenied):
        fixture["repo"].resident_detail(None, receipt.report_id)
    with fixture["sessions"].begin() as session:
        session.execute(
            update(Membership)
            .where(Membership.user_id == fixture["users"][REVIEWER.subject])
            .values(state="SUSPENDED")
        )
    with pytest.raises(NotFound):
        fixture["repo"].authority_detail(REVIEWER, receipt.case_id)
    with fixture["sessions"].begin() as session:
        session.execute(
            update(Identity)
            .where(Identity.id == fixture["users"][RESIDENT.subject])
            .values(active=False)
        )
    with pytest.raises(AccessDenied):
        accept(fixture)


def test_unknown_routing_accepts_unassigned_without_client_override(fixture):
    fixture["repo"].triage_unit_id = None
    receipt = accept(fixture)
    with fixture["sessions"]() as session:
        assert session.get(Case, receipt.case_id).assigned_unit_id is None
    with pytest.raises(NotFound):
        fixture["repo"].authority_detail(REVIEWER, receipt.case_id)
    with pytest.raises(ValidationError):
        ReportSubmission(**submission().model_dump(), unit_id=fixture["unit"])
    with pytest.raises(ValidationError):
        ReportSubmission(**submission().model_dump(), user_id=fixture["users"][OTHER.subject])


def test_google_raw_and_unknown_sources_fail_closed(fixture):
    receipt = accept(fixture)
    with pytest.raises(ValidationError):
        FragmentInput(payload={"kind": "google_aq", "aqi": 42}, retrieved_at=fixture["clock"][0])
    with pytest.raises(ValidationError):
        FirmsPayload(dataset="VIIRS_NOAA20_NRT", detection_count=0, google_aq=42)
    fresh = DurableRepository(fixture["sessions"])
    with pytest.raises(AccessDenied):
        fresh.append_evidence(
            REVIEWER,
            receipt.case_id,
            request_id=initial_request(fixture, receipt.report_id),
            fragments=[
                FragmentInput(
                    payload=FirmsPayload(dataset="VIIRS_NOAA20_NRT", detection_count=0),
                    retrieved_at=fixture["clock"][0],
                )
            ],
        )
    with pytest.raises(IntegrityError), fixture["sessions"].begin() as session:
        version = EvidenceVersion(
            case_id=receipt.case_id,
            request_id=uuid4(),
            version=1,
            created_at=fixture["clock"][0],
            expires_at=fixture["clock"][0] + timedelta(days=1),
        )
        session.add(version)
        session.flush()
        session.add(
            EvidenceFragment(
                version_id=version.id,
                source="GOOGLE_AQ",
                policy_version="bad",
                retrieved_at=fixture["clock"][0],
                expires_at=fixture["clock"][0],
                payload={"aqi": 42},
                state="AVAILABLE",
            )
        )


def test_local_adapter_rejects_paths_symlinks_and_invalid_uploads(fixture, tmp_path):
    for key in ("../image", "/etc/passwd", "image.jpg", "0" * 31, "A" * 32):
        for method in (fixture["store"].read, fixture["store"].delete, fixture["store"].exists):
            with pytest.raises(ValueError):
                method(key)
    with pytest.raises(ValueError):
        LocalPrivateMediaStore((tmp_path / "public" / "images").resolve())
    symlink = uuid4().hex
    target = tmp_path / "outside"
    target.write_bytes(b"outside")
    (fixture["store"].root / symlink).symlink_to(target)
    with pytest.raises(OSError):
        fixture["store"].read(symlink)
    fixture["store"].delete(symlink)
    assert target.read_bytes() == b"outside"
    for data, mime in (
        (b"bad", "image/jpeg"),
        (image_bytes(), "image/png"),
        (b"x" * 4_000_001, "image/jpeg"),
    ):
        with pytest.raises(ValueError):
            fixture["media"].stage(RESIDENT, data, mime)
    assert not fixture["store"].inventory()


def test_database_rejects_sqlite_and_nonlocal_without_verified_tls():
    with pytest.raises(ValueError):
        database("sqlite://")
    with pytest.raises(ValueError):
        database("postgresql+psycopg://not-a-real-host.invalid/pilot?sslmode=require")
