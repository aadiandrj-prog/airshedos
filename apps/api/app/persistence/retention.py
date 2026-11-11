"""Explicit bounded maintenance pass, not the future analysis job worker.

Read guards apply even when this process is down. Physical cleanup must be scheduled
at least every minute before collecting real retained data. Failures remain retryable;
no successful purge receipt is produced while an object deletion failed.
"""

from datetime import timedelta

from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert

from app.persistence.models import (
    AbuseWindow,
    AccessAudit,
    AnalysisAdmission,
    AnalysisRun,
    AuthSession,
    AuthSessionSecret,
    Case,
    EvidenceFragment,
    EvidenceRedaction,
    EvidenceVersion,
    IdempotencyKey,
    InformationRequest,
    InternalNote,
    Job,
    MaintenanceHeartbeat,
    Media,
    MembershipProposal,
    PrivacyRequest,
    ProcessingMetric,
    Report,
    ReporterUpdate,
    ReportSupplement,
    ReviewEvent,
    VerificationTask,
)


class RetentionService:
    def __init__(self, repository, store):
        self.repo, self.store = repository, store

    def _delete_media(self, session, media):
        # Do not clear the key on failure: the next pass must retry this object.
        # Row state is unnecessary for authorization: parent suppression/expiry denies reads.
        if media.object_key:
            self.store.delete(media.object_key)
        media.object_key = media.sha256 = media.size_bytes = None
        media.state = "DELETED"

    def sweep(self, *, limit=100):
        if not 1 <= limit <= 1000:
            raise ValueError("Maintenance batch limit must be 1–1000")
        now, repo = self.repo.clock(), self.repo
        if getattr(self.store, "requires_empty_media", False):
            from app.persistence.contracts import PersistenceError

            with repo.sessions() as session:
                if session.scalar(select(Media.id).where(Media.object_key.is_not(None)).limit(1)):
                    raise PersistenceError("Private storage required for existing media custody")
        counts = {"reports": 0, "media": 0, "fragments": 0, "orphans": 0, "tombstones": 0}
        # Reports first: locks order matches report/case mutations. Never wait on providers.
        with repo.sessions.begin() as session:
            reports = session.scalars(
                select(Report)
                .where(
                    Report.purged_at.is_(None),
                    or_(Report.deletion_state == "SUPPRESSED", Report.content_expires_at <= now),
                )
                .order_by(Report.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
            for report in reports:
                case = session.scalar(
                    select(Case).where(Case.report_id == report.id).with_for_update()
                )
                supplements = select(ReportSupplement.id).where(
                    ReportSupplement.report_id == report.id
                )
                for media in session.scalars(
                    select(Media)
                    .where(or_(Media.report_id == report.id, Media.supplement_id.in_(supplements)))
                    .with_for_update()
                ):
                    self._delete_media(session, media)
                    counts["media"] += 1
                report.description = report.declared_category = None
                report.reported_place = None
                case.external_reference = None
                for entry in session.scalars(
                    select(ReviewEvent).where(ReviewEvent.case_id == case.id)
                ):
                    entry.reason = None
                report.reported_latitude = report.reported_longitude = None
                report.declared_capture_at = None
                report.capture_time_basis = "unknown"
                report.deletion_state, report.purged_at = "PURGED", now
                report.audit_expires_at = max(
                    report.audit_expires_at, now + timedelta(days=repo.retention.audit_days)
                )
                privacy = session.scalar(
                    select(PrivacyRequest).where(PrivacyRequest.report_id == report.id)
                )
                if privacy is None:
                    privacy = PrivacyRequest(
                        report_id=report.id,
                        requested_at=now,
                        purge_due_at=now,
                        ledger_expires_at=report.audit_expires_at,
                    )
                    session.add(privacy)
                privacy.purged_at = now
                for key in session.scalars(
                    select(IdempotencyKey).where(IdempotencyKey.report_id == report.id)
                ):
                    key.fingerprint, key.tombstone = None, True
                    key.consumed_until = report.audit_expires_at
                for table, fields in (
                    (InternalNote, ("body",)),
                    (ReporterUpdate, ("message",)),
                    (VerificationTask, ("instructions", "outcome")),
                ):
                    for row in session.scalars(select(table).where(table.case_id == case.id)):
                        for field in fields:
                            setattr(row, field, None)
                        if isinstance(row, VerificationTask) and row.state != "COMPLETED":
                            row.state = "CANCELLED"
                for supplement in session.scalars(
                    select(ReportSupplement).where(ReportSupplement.report_id == report.id)
                ):
                    supplement.body = None
                for request in session.scalars(
                    select(InformationRequest).where(InformationRequest.case_id == case.id)
                ):
                    request.prompt, request.state = None, "CLOSED"
                for job in session.scalars(select(Job).where(Job.report_id == report.id)):
                    if job.state in {"PENDING", "RUNNING", "RETRY_WAIT"}:
                        job.state = "CANCELLED"
                        job.lease_token = job.lease_expires_at = None
                for attempt in session.scalars(
                    select(AnalysisRun).where(AnalysisRun.report_id == report.id)
                ):
                    if attempt.state in {"PENDING", "RUNNING"}:
                        attempt.state, attempt.ended_at = "CANCELLED", now
                for version in session.scalars(
                    select(EvidenceVersion).where(EvidenceVersion.case_id == case.id)
                ):
                    version.input_fingerprint = None
                    self._redact(session, version.id, now, deleted=True)
                counts["reports"] += 1
        # Independent source expiries also remove input hashes and all expired source payloads.
        with repo.sessions.begin() as session:
            versions = session.scalars(
                select(EvidenceVersion)
                .where(
                    EvidenceVersion.expires_at <= now,
                    EvidenceVersion.input_fingerprint.is_not(None),
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
            for version in versions:
                version.input_fingerprint = None
                counts["fragments"] += self._redact(session, version.id, now)
            # Versions already lost an input hash at an earlier source expiry: still purge
            # later source expiries. There is no aggregate payload/derived copy in this phase.
            fragments = session.scalars(
                select(EvidenceFragment)
                .where(
                    EvidenceFragment.state == "AVAILABLE",
                    EvidenceFragment.expires_at <= now,
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            ).all()
            for fragment in fragments:
                self._redact_fragment(session, fragment, now, "EXPIRED_BY_SOURCE_POLICY")
                counts["fragments"] += 1
        with repo.sessions.begin() as session:
            for media in session.scalars(
                select(Media)
                .where(
                    Media.state != "DELETED",
                    or_(Media.expires_at <= now, Media.state == "DELETING"),
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            ):
                self._delete_media(session, media)
                counts["media"] += 1
            # Intents precede object writes. Unknown aged objects are crash/failed-commit
            # leftovers; a grace interval avoids racing an in-progress staging operation.
            for key, modified in self.store.inventory():
                if now.timestamp() - modified < repo.retention.staging_seconds:
                    continue
                row = session.scalar(select(Media).where(Media.object_key == key))
                if row is None:
                    self.store.delete(key)
                    counts["orphans"] += 1
                if counts["orphans"] >= limit:
                    break
        self._expire_audit(now, limit, counts)
        with repo.sessions.begin() as session:
            overdue = any(
                (
                    session.scalar(
                        select(Report.id)
                        .where(
                            Report.purged_at.is_(None),
                            or_(
                                Report.deletion_state == "SUPPRESSED",
                                Report.content_expires_at <= now,
                            ),
                        )
                        .limit(1)
                    ),
                    session.scalar(
                        select(Media.id)
                        .where(
                            Media.state != "DELETED",
                            or_(Media.state == "DELETING", Media.expires_at <= now),
                        )
                        .limit(1)
                    ),
                    session.scalar(
                        select(EvidenceFragment.id)
                        .where(
                            EvidenceFragment.state == "AVAILABLE",
                            EvidenceFragment.expires_at <= now,
                        )
                        .limit(1)
                    ),
                )
            )
            if not overdue and counts["orphans"] < limit:
                session.execute(
                    insert(MaintenanceHeartbeat)
                    .values(name="retention", succeeded_at=repo.clock())
                    .on_conflict_do_update(
                        index_elements=[MaintenanceHeartbeat.name],
                        set_={"succeeded_at": repo.clock()},
                    )
                )
        return counts

    def _redact(self, session, version_id, now, deleted=False):
        count = 0
        for f in session.scalars(
            select(EvidenceFragment)
            .where(
                EvidenceFragment.version_id == version_id,
                EvidenceFragment.state == "AVAILABLE",
            )
            .with_for_update()
        ):
            if deleted or f.expires_at <= now:
                self._redact_fragment(
                    session, f, now, "DELETED" if deleted else "EXPIRED_BY_SOURCE_POLICY"
                )
                count += 1
        return count

    @staticmethod
    def _redact_fragment(session, fragment, now, reason):
        fragment.payload = fragment.content_sha256 = None
        fragment.state = reason
        session.add(EvidenceRedaction(fragment_id=fragment.id, reason=reason, created_at=now))

    def _expire_audit(self, now, limit, counts):
        with self.repo.sessions.begin() as session:
            for report in session.scalars(
                select(Report)
                .where(
                    Report.purged_at.is_not(None),
                    Report.audit_expires_at <= now,
                )
                .limit(limit)
                .with_for_update(skip_locked=True)
            ):
                case = session.scalar(select(Case).where(Case.report_id == report.id))
                case.latest_evidence_version_id = None
                session.flush()
                versions = select(EvidenceVersion.id).where(EvidenceVersion.case_id == case.id)
                fragments = select(EvidenceFragment.id).where(
                    EvidenceFragment.version_id.in_(versions)
                )
                supplements = select(ReportSupplement.id).where(
                    ReportSupplement.report_id == report.id
                )
                session.execute(
                    delete(Media).where(
                        or_(Media.report_id == report.id, Media.supplement_id.in_(supplements))
                    )
                )
                session.execute(
                    delete(ReportSupplement).where(ReportSupplement.report_id == report.id)
                )
                session.execute(
                    delete(InformationRequest).where(InformationRequest.case_id == case.id)
                )
                session.execute(
                    delete(EvidenceRedaction).where(EvidenceRedaction.fragment_id.in_(fragments))
                )
                for table in (ReviewEvent, InternalNote, ReporterUpdate, VerificationTask):
                    session.execute(delete(table).where(table.case_id == case.id))
                session.execute(
                    delete(EvidenceFragment).where(EvidenceFragment.version_id.in_(versions))
                )
                session.execute(delete(EvidenceVersion).where(EvidenceVersion.case_id == case.id))
                session.execute(
                    delete(AnalysisAdmission).where(AnalysisAdmission.case_id == case.id)
                )
                session.delete(case)
                session.flush()
                for table in (IdempotencyKey, AnalysisRun, Job, Media, PrivacyRequest):
                    session.execute(delete(table).where(table.report_id == report.id))
                session.delete(report)
                counts["tombstones"] += 1
            # Unattached stage tombstones carry no report audit requirement.
            session.execute(
                delete(Media).where(
                    Media.report_id.is_(None),
                    Media.state == "DELETED",
                    Media.created_at <= now - timedelta(days=self.repo.retention.audit_days),
                )
            )
            session.execute(delete(ProcessingMetric).where(ProcessingMetric.expires_at <= now))
            session.execute(delete(AbuseWindow).where(AbuseWindow.expires_at <= func.now()))
            session.execute(
                delete(AnalysisAdmission).where(AnalysisAdmission.expires_at <= func.now())
            )
            session.execute(delete(AccessAudit).where(AccessAudit.expires_at <= now))
            session.execute(delete(MembershipProposal).where(MembershipProposal.expires_at <= now))
            expired = select(AuthSession.id).where(
                or_(
                    AuthSession.revoked_at.is_not(None),
                    AuthSession.idle_expires_at <= now,
                    AuthSession.absolute_expires_at <= now,
                )
            )
            session.execute(
                delete(AuthSessionSecret).where(AuthSessionSecret.session_id.in_(expired))
            )
            # Keep consumed SDK-key tombstones through every possible token/refresh lifetime.
            session.execute(
                delete(AuthSession).where(
                    AuthSession.absolute_expires_at <= now - timedelta(minutes=11)
                )
            )
