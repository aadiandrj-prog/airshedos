"""Offline recovery; a manifest must come from the latest authoritative erasure ledger.

Not an HTTP route. Quarantine uses a fresh deployment epoch held outside backups.
A hash checks file integrity, not provenance, completeness or deletion by itself.
"""

import hashlib
import os
from datetime import timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import delete, func, select, text, update

from app.persistence.contracts import AccessDenied, PersistenceError, StrictModel
from app.persistence.models import (
    AnalysisAdmission,
    AnalysisRun,
    AuthSession,
    AuthSessionSecret,
    Case,
    EvidenceVersion,
    Identity,
    Job,
    MaintenanceHeartbeat,
    Media,
    Membership,
    OperatorGrant,
    PrivacyRequest,
    RecoveryControl,
    Report,
    WorkerHeartbeat,
)
from app.persistence.retention import RetentionService


class RecoveryManifest(StrictModel):
    schema_version: Literal["seva_erasure_manifest_v1"] = "seva_erasure_manifest_v1"
    created_at: AwareDatetime
    covers_since: AwareDatetime
    report_tombstones: list[UUID] = Field(max_length=100000)
    media_tombstones: list[UUID] = Field(max_length=100000)
    report_deadlines: dict[UUID, AwareDatetime] = Field(max_length=100000)
    media_deadlines: dict[UUID, AwareDatetime] = Field(max_length=100000)
    inactive_users: list[UUID] = Field(max_length=100000)

    @model_validator(mode="after")
    def window(self):
        if not self.created_at - timedelta(days=7) <= self.covers_since <= self.created_at:
            raise ValueError("Manifest coverage must fit the seven-day backup ceiling")
        return self


def write_manifest(path: Path, manifest):
    if not path.is_absolute() or path.parent.is_symlink() or path.parent.stat().st_mode & 0o077:
        raise ValueError("Absolute path in a private directory required")
    data = manifest.model_dump_json().encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    return hashlib.sha256(data).hexdigest()


def read_manifest(path: Path, expected_sha256):
    if path.is_symlink() or path.stat().st_size > 20_000_000 or path.stat().st_mode & 0o077:
        raise ValueError("Bounded private manifest file required")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("Manifest integrity mismatch")
    return RecoveryManifest.model_validate_json(data)


class RecoveryManager:
    def __init__(self, repo, store, *, database_role):
        self.repo, self.store, self.database_role = repo, store, database_role
        if not database_role:
            raise ValueError("Approved management login required")

    def connection(self, session):
        if session.scalar(text("SELECT session_user")) != self.database_role:
            raise AccessDenied("Approved offline management database login required")

    def initialise_empty(self, epoch):
        with self.repo.sessions.begin() as session:
            self.connection(session)
            row = session.get(RecoveryControl, "pilot", with_for_update=True)
            if (
                row is None
                or row.epoch is not None
                or session.scalar(select(func.count()).select_from(Identity))
                or session.scalar(select(func.count()).select_from(Report))
                or session.scalar(select(func.count()).select_from(Media))
            ):
                raise AccessDenied("Empty bootstrap cannot release existing/restored records")
            row.epoch, row.state = epoch, "READY"
            row.released_at = session.scalar(select(func.clock_timestamp()))

    def export(self):
        # READ COMMITTED is insufficient for a consistent cutover manifest. Freeze the
        # source writes operationally and use one repeatable-read snapshot for export.
        with self.repo.sessions.begin() as session:
            session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            self.connection(session)
            now = session.scalar(select(func.clock_timestamp()))
            reports = list(session.scalars(select(Report)))
            media = list(session.scalars(select(Media)))
            tombstones = set(session.scalars(select(PrivacyRequest.report_id)))
            return RecoveryManifest(
                created_at=now,
                covers_since=now - timedelta(days=7),
                report_tombstones=list(
                    tombstones | {r.id for r in reports if r.deletion_state != "ACTIVE"}
                ),
                media_tombstones=[m.id for m in media if m.state in {"DELETED", "DELETING"}],
                report_deadlines={r.id: r.content_expires_at for r in reports},
                media_deadlines={m.id: m.expires_at for m in media},
                inactive_users=list(
                    session.scalars(select(Identity.id).where(Identity.active.is_(False)))
                ),
            )

    def quarantine(self, epoch):
        with self.repo.sessions.begin() as session:
            self.connection(session)
            row = session.get(RecoveryControl, "pilot", with_for_update=True)
            if row is None or row.epoch == epoch:
                raise AccessDenied("A fresh out-of-band recovery epoch is required")
            row.epoch, row.state = epoch, "QUARANTINED"
            row.manifest_sha256 = row.applied_at = row.released_at = None
            session.execute(delete(MaintenanceHeartbeat))
            session.execute(delete(WorkerHeartbeat))
            # Nothing restored is an active job/session/grant. Original case/evidence
            # records remain; reviewer/operator access needs deliberate re-provisioning.
            session.execute(delete(AuthSessionSecret))
            session.execute(delete(AuthSession))
            session.execute(delete(AnalysisAdmission))
            session.execute(delete(OperatorGrant))
            session.execute(update(Membership).values(state="SUSPENDED"))
            session.execute(
                update(Job)
                .where(Job.state.in_(["PENDING", "RUNNING", "RETRY_WAIT"]))
                .values(
                    state="CANCELLED",
                    safe_reason="RESTORE_QUARANTINE",
                    lease_token=None,
                    lease_expires_at=None,
                )
            )
            session.execute(
                update(AnalysisRun)
                .where(AnalysisRun.state.in_(["PENDING", "RUNNING"]))
                .values(state="CANCELLED", safe_reason="RESTORE_QUARANTINE")
            )

    def apply(self, epoch, manifest, *, backup_at, expected_sha256):
        with self.repo.sessions.begin() as session:
            self.connection(session)
            row = session.get(RecoveryControl, "pilot", with_for_update=True)
            now = session.scalar(select(func.clock_timestamp()))
            if (
                row is None
                or row.state != "QUARANTINED"
                or row.epoch != epoch
                or backup_at.tzinfo is None
                or not manifest.covers_since <= backup_at <= manifest.created_at
                or not now - timedelta(minutes=5)
                <= manifest.created_at
                <= now + timedelta(seconds=5)
            ):
                raise AccessDenied(
                    "Fresh complete-cutover manifest and quarantined target required"
                )
            # The CLI verified the raw file. Direct callers provide the exact canonical digest.
            if hashlib.sha256(manifest.model_dump_json().encode()).hexdigest() != expected_sha256:
                raise ValueError("Canonical manifest integrity mismatch")
            if len(expected_sha256) != 64 or any(
                c not in "0123456789abcdef" for c in expected_sha256
            ):
                raise ValueError("Manifest integrity identifier required")
            known_reports = set(manifest.report_deadlines) | set(manifest.report_tombstones)
            known_media = set(manifest.media_deadlines) | set(manifest.media_tombstones)
            if (
                set(session.scalars(select(Report.id))) - known_reports
                or set(session.scalars(select(Media.id))) - known_media
            ):
                raise AccessDenied("Manifest omits restored records; reconcile the complete ledger")
            for report in session.scalars(select(Report).with_for_update()):
                deadline = manifest.report_deadlines.get(report.id)
                if deadline is not None:
                    report.content_expires_at = min(report.content_expires_at, deadline)
                if report.id in manifest.report_tombstones and report.deletion_state == "ACTIVE":
                    report.deletion_state = "SUPPRESSED"
            for media in session.scalars(select(Media).with_for_update()):
                deadline = manifest.media_deadlines.get(media.id)
                shortened = deadline is not None and deadline < media.expires_at
                if deadline is not None:
                    media.expires_at = min(media.expires_at, deadline)
                if media.id in manifest.media_tombstones:
                    media.state, media.expires_at = "DELETING", now
                if shortened or media.id in manifest.media_tombstones:
                    case = session.scalar(select(Case).where(Case.report_id == media.report_id))
                    if case:
                        for version in session.scalars(
                            select(EvidenceVersion).where(EvidenceVersion.case_id == case.id)
                        ):
                            version.input_fingerprint = None
                            RetentionService(self.repo, self.store)._redact(
                                session, version.id, now, deleted=True
                            )
            if manifest.inactive_users:
                session.execute(
                    update(Identity)
                    .where(Identity.id.in_(manifest.inactive_users))
                    .values(active=False)
                )
            row.manifest_sha256, row.applied_at = expected_sha256, now
        # Still quarantined if any physical cleanup fails, or a bounded sweep leaves backlog.
        service = RetentionService(self.repo, self.store)
        for _ in range(100):
            counts = service.sweep(limit=1000)
            with self.repo.sessions() as session:
                if session.get(MaintenanceHeartbeat, "retention") is not None:
                    return counts
        raise PersistenceError("Restore cleanup backlog; remain quarantined and retry")

    def release(self, epoch, *, expected_sha256):
        with self.repo.sessions.begin() as session:
            self.connection(session)
            row = session.get(RecoveryControl, "pilot", with_for_update=True)
            now = session.scalar(select(func.clock_timestamp()))
            heartbeat = session.get(MaintenanceHeartbeat, "retention")
            if (
                row is None
                or row.epoch != epoch
                or row.state != "QUARANTINED"
                or not row.applied_at
                or row.manifest_sha256 != expected_sha256
                or heartbeat is None
                or heartbeat.succeeded_at < row.applied_at
                or heartbeat.succeeded_at < now - timedelta(seconds=120)
            ):
                raise AccessDenied("Manifest replay and completed physical cleanup required")
            row.state, row.released_at = "READY", now
