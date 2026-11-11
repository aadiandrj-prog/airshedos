import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.access.limits import AdmissionLimits, charge
from app.persistence.contracts import (
    Acceptance,
    AccessDenied,
    AuthorityCaseDetail,
    Conflict,
    FragmentInput,
    Gone,
    InformationRequestRead,
    Location,
    MediaRead,
    NotFound,
    Principal,
    ProcessingRead,
    PublishedUpdate,
    ReportSubmission,
    ResidentReportDetail,
    Retention,
    SupplementRead,
)
from app.persistence.models import (
    AnalysisAdmission,
    AnalysisRun,
    AuthSession,
    Case,
    EvidenceFragment,
    EvidenceVersion,
    IdempotencyKey,
    Identity,
    InformationRequest,
    InternalNote,
    Job,
    Media,
    Membership,
    PrivacyRequest,
    Report,
    ReporterUpdate,
    ReportSupplement,
    ReviewEvent,
    Unit,
    VerificationTask,
)
from app.persistence.policies import GOOGLE_NO_STORE_POLICY, POLICIES

TRANSITIONS = {
    "NEW": {"UNDER_REVIEW"},
    "UNDER_REVIEW": {"ACKNOWLEDGED", "MONITORING", "CLOSED_NO_ACTION"},
    "ACKNOWLEDGED": {"MONITORING", "CLOSED_NO_ACTION"},
    "MONITORING": {"UNDER_REVIEW", "ACKNOWLEDGED", "CLOSED_NO_ACTION"},
    "CLOSED_NO_ACTION": set(),
}


def utcnow():
    return datetime.now(UTC)


def fingerprint(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class DurableRepository:
    def __init__(
        self,
        sessions,
        *,
        triage_unit_id: UUID | None = None,
        retention: Retention | None = None,
        clock=utcnow,
        provider_retention_reviewed=False,
        require_session=False,
        limits: AdmissionLimits | None = None,
        require_maintenance=False,
        release_epoch=None,
    ):
        self.sessions = sessions
        self.release_epoch = release_epoch
        self.triage_unit_id = triage_unit_id  # Trusted server config, never a submission field.
        self.retention = retention or Retention()
        self.clock = clock
        self.provider_retention_reviewed = provider_retention_reviewed
        self.require_session = require_session
        self.limits = limits or AdmissionLimits()
        self.require_maintenance = require_maintenance

    def identity(self, session, principal: Principal, *, lock=False):
        if self.release_epoch is not None:
            from app.operations.readiness import require_released

            require_released(session, self.release_epoch)
        if not isinstance(principal, Principal):
            raise AccessDenied("Verified principal context required")
        query = select(Identity).where(
            Identity.issuer == principal.issuer,
            Identity.subject == principal.subject,
            Identity.active.is_(True),
        )
        # Shared identity/membership locks fence revocation until a mutation commits.
        if lock:
            query = query.with_for_update(read=True)
        user = session.scalar(query)
        if user is None:
            raise AccessDenied("Active account required")
        if self.require_session:
            session_query = select(
                AuthSession.id, AuthSession.idle_expires_at, AuthSession.absolute_expires_at
            ).where(
                AuthSession.id == principal.session_id,
                AuthSession.user_id == user.id,
                AuthSession.issuer == principal.issuer,
                AuthSession.subject == principal.subject,
                AuthSession.revoked_at.is_(None),
                AuthSession.idle_expires_at > self.clock(),
                AuthSession.absolute_expires_at > self.clock(),
            )
            if lock:
                session_query = session_query.with_for_update(read=True)
            active_session = session.execute(session_query).first()
            if active_session is None or min(active_session[1:]) <= self.clock():
                raise AccessDenied("Active application session required")
        return user

    def _case(self, session, principal, case_id, *, lock=False):
        from app.processing.queue import WorkerLease, guarded_case

        if isinstance(principal, WorkerLease):
            return guarded_case(self, session, principal, case_id, lock=lock)
        user = self.identity(session, principal, lock=lock)
        query = (
            select(Case, Report, Membership)
            .join(Report, Report.id == Case.report_id)
            .join(Membership, Membership.unit_id == Case.assigned_unit_id)
            .join(Unit, Unit.id == Case.assigned_unit_id)
            .where(
                Case.id == case_id,
                Membership.user_id == user.id,
                Membership.state == "ACTIVE",
                Membership.approved_by.is_not(None),
                Membership.approved_at.is_not(None),
                Unit.approved_at.is_not(None),
                Unit.is_prototype.is_(False),
                Report.deletion_state == "ACTIVE",
                Report.content_expires_at > self.clock(),
            )
        )
        if principal.unit_id is not None:
            query = query.where(Case.assigned_unit_id == principal.unit_id)
        if lock:
            candidate = session.execute(query).first()
            if candidate is None:
                raise NotFound("Case not found")
            # Explicit statements establish report -> case ordering, independent of the
            # PostgreSQL join planner. Reload after waits; recheck scope under grant locks.
            session.scalar(
                select(Report)
                .where(Report.id == candidate[1].id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            session.scalar(
                select(Case)
                .where(Case.id == case_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            query = query.with_for_update(of=[Membership, Unit], read=True).execution_options(
                populate_existing=True
            )
        row = session.execute(query).first()
        if row is None or row[1].content_expires_at <= self.clock():
            raise NotFound("Case not found")
        return user, row[0], row[1]

    def _owned_report(self, session, principal, report_id, *, lock=False):
        user = self.identity(session, principal, lock=lock)
        query = select(Report).where(
            Report.id == report_id,
            Report.reporter_user_id == user.id,
            Report.deletion_state == "ACTIVE",
            Report.content_expires_at > self.clock(),
        )
        if lock:
            query = query.with_for_update()
        report = session.scalar(query)
        if report is None or report.content_expires_at <= self.clock():
            raise NotFound("Report not found")
        return user, report

    def _schedule(self, session, report, *, kind, has_media, requested_by=None):
        request_id = uuid4()
        session.add(
            Job(
                report_id=report.id,
                request_id=request_id,
                kind=kind,
                state="PENDING",
                created_at=session.scalar(select(func.clock_timestamp())),
                next_run_at=None,  # Immediately due; only PostgreSQL computes retry/lease times.
                requested_by=requested_by,
                authorized_unit_id=session.scalar(
                    select(Case.assigned_unit_id).where(Case.report_id == report.id)
                ),
            )
        )
        for stage in ("VISUAL", "ENVIRONMENT", "CORROBORATION", "FORECAST"):
            not_applicable = stage == "VISUAL" and not has_media or stage == "FORECAST"
            reason = (
                ("NO_IMAGE" if stage == "VISUAL" else "NOT_RETAINED_BY_POLICY")
                if not_applicable
                else None
            )
            session.add(
                AnalysisRun(
                    report_id=report.id,
                    request_id=request_id,
                    stage=stage,
                    attempt=0,
                    state="NOT_APPLICABLE" if not_applicable else "PENDING",
                    safe_reason=reason,
                    ended_at=self.clock() if not_applicable else None,
                )
            )
        return request_id

    def create_report(
        self,
        principal: Principal,
        submission: ReportSubmission,
        *,
        key: UUID,
        key_created_at: datetime,
    ) -> Acceptance:
        if not isinstance(submission, ReportSubmission) or not isinstance(key, UUID):
            raise ValueError("Validated submission and UUID idempotency key required")
        if key_created_at.tzinfo is None or key_created_at.utcoffset() is None:
            raise ValueError("Aware idempotency creation time required")
        envelope = submission.model_dump(mode="json") | {
            "key_created_at": key_created_at.astimezone(UTC).isoformat()
        }
        digest = fingerprint(envelope)
        now = self.clock()
        with self.sessions.begin() as session:
            user = self.identity(session, principal, lock=True)
            # Serialize only duplicate principal/operation/key, including first concurrent insert.
            # PostgreSQL transaction advisory lock releases on commit/rollback/process loss.
            from sqlalchemy import text

            lock_key = int.from_bytes(
                hashlib.sha256(f"{user.id}:CREATE_REPORT:{key}".encode()).digest()[:8],
                signed=True,
            )
            session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
            now = self.clock()  # A retry can have waited for another transaction.
            prior = session.scalar(
                select(IdempotencyKey).where(
                    IdempotencyKey.principal_id == user.id,
                    IdempotencyKey.operation == "CREATE_REPORT",
                    IdempotencyKey.key == key,
                )
            )
            if prior:
                report = session.get(Report, prior.report_id)
                if (
                    prior.tombstone
                    or report.deletion_state != "ACTIVE"
                    or report.content_expires_at <= now
                ):
                    raise Gone("Submission is no longer available")
                if prior.fingerprint != digest:
                    raise Conflict("Idempotency key already used with different input")
                case = session.scalar(select(Case).where(Case.report_id == report.id))
                return self._acceptance(report, case, replayed=True)
            if key_created_at < now - timedelta(hours=24):
                raise Gone("New idempotency key is too old")
            if key_created_at > now + timedelta(seconds=60):
                raise ValueError("Idempotency creation time is in the future")
            charge(
                session,
                scope=user.id,
                rule="REPORT_INTAKE",
                period="day",
                maximum=self.limits.reports_per_day,
            )
            unit_id = self.triage_unit_id
            if unit_id is not None:
                unit = session.scalar(select(Unit).where(Unit.id == unit_id).with_for_update())
                if unit is None or unit.approved_at is None or unit.is_prototype:
                    raise ValueError("Trusted triage unit is not approved")
            media = None
            if submission.media_id:
                media = session.scalar(
                    select(Media)
                    .where(Media.id == submission.media_id, Media.owner_id == user.id)
                    .with_for_update()
                )
                if media is None or media.state != "READY" or media.expires_at <= self.clock():
                    raise NotFound("Ready private media not found")
            report = Report(
                reporter_user_id=user.id,
                accepted_at=now,
                description=submission.description,
                reported_place=submission.reported_place,
                declared_category=submission.declared_category,
                reported_latitude=submission.reported_latitude,
                reported_longitude=submission.reported_longitude,
                declared_capture_at=submission.declared_capture_at,
                capture_time_basis=(
                    "resident_declared" if submission.declared_capture_at else "unknown"
                ),
                content_expires_at=now + timedelta(days=self.retention.report_days),
                audit_expires_at=now + timedelta(days=self.retention.audit_days),
            )
            session.add(report)
            session.flush()
            case = Case(report_id=report.id, assigned_unit_id=unit_id, created_at=now)
            session.add(case)
            session.flush()
            if media:
                media.report_id, media.state = report.id, "ATTACHED"
                media.expires_at = min(
                    report.content_expires_at,
                    media.created_at + timedelta(days=self.retention.media_days),
                )
            self._schedule(session, report, kind="PROCESS_REPORT", has_media=media is not None)
            session.add(
                ReporterUpdate(
                    case_id=case.id,
                    status="RECEIVED",
                    message=None,
                    published_at=now,
                    case_revision=0,
                    expires_at=report.content_expires_at,
                )
            )
            session.add(
                IdempotencyKey(
                    principal_id=user.id,
                    operation="CREATE_REPORT",
                    key=key,
                    fingerprint=digest,
                    key_created_at=key_created_at,
                    report_id=report.id,
                    consumed_until=report.audit_expires_at,
                )
            )
            result = self._acceptance(report, case)
        # Context manager has committed before any caller sees a receipt.
        return result

    @staticmethod
    def _acceptance(report, case, replayed=False):
        return Acceptance(
            report_id=report.id,
            case_id=case.id,
            receipt_id=report.receipt_id,
            accepted_at=report.accepted_at,
            replayed=replayed,
        )

    def resident_detail(self, principal, report_id) -> ResidentReportDetail:
        with self.sessions.begin() as session:
            _, report = self._owned_report(session, principal, report_id)
            case = session.scalar(select(Case).where(Case.report_id == report.id))
            updates = session.scalars(
                select(ReporterUpdate)
                .where(
                    ReporterUpdate.case_id == case.id,
                    ReporterUpdate.expires_at > self.clock(),
                )
                .order_by(
                    ReporterUpdate.published_at,
                    ReporterUpdate.case_revision.nullsfirst(),
                    ReporterUpdate.id,
                )
            ).all()
            media = session.scalar(select(Media).where(Media.report_id == report.id))
            requests = session.scalars(
                select(InformationRequest)
                .where(InformationRequest.case_id == case.id)
                .order_by(InformationRequest.created_at, InformationRequest.id)
            ).all()
            supplements = session.scalars(
                select(ReportSupplement)
                .where(ReportSupplement.report_id == report.id)
                .order_by(ReportSupplement.accepted_at, ReportSupplement.id)
            ).all()
            visible = [(u.id, u.published_at, u.case_revision) for u in updates] + [
                (item.id, item.accepted_at, item.case_revision) for item in supplements
            ]
            visible.sort(key=lambda item: (item[1], item[2] or 0, str(item[0])))
            public_order = {item[0]: index for index, item in enumerate(visible)}
            return ResidentReportDetail(
                content_expires_at=report.content_expires_at,
                id=report.id,
                receipt_id=report.receipt_id,
                accepted_at=report.accepted_at,
                description=report.description,
                reported_place=report.reported_place,
                declared_category=report.declared_category,
                reported_location=Location(
                    latitude=report.reported_latitude, longitude=report.reported_longitude
                ),
                declared_capture_at=report.declared_capture_at,
                capture_time_basis=report.capture_time_basis,
                media=self.media_projection(media) if not report.withdrawn_at else None,
                reporter_status=updates[-1].status,
                published_updates=[
                    PublishedUpdate(
                        id=u.id,
                        status=u.status,
                        message=u.message,
                        published_at=u.published_at,
                        timeline_order=public_order[u.id],
                    )
                    for u in updates
                ],
                processing=self.processing_projection(session, report, case),
                withdrawn_at=report.withdrawn_at,
                deletion_state=report.deletion_state,
                information_requests=[
                    InformationRequestRead(
                        id=r.id,
                        prompt=r.prompt if r.expires_at > self.clock() else None,
                        state=r.state if r.expires_at > self.clock() else "EXPIRED",
                        created_at=r.created_at,
                        expires_at=r.expires_at,
                    )
                    for r in requests
                ],
                supplements=[
                    SupplementRead(
                        id=s.id,
                        request_id=s.request_id,
                        body=s.body if s.expires_at > self.clock() else None,
                        accepted_at=s.accepted_at,
                        timeline_order=public_order[s.id],
                        media=self.media_projection(
                            session.scalar(select(Media).where(Media.supplement_id == s.id))
                        )
                        if s.expires_at > self.clock() and not report.withdrawn_at
                        else None,
                    )
                    for s in supplements
                ],
            )

    def processing_projection(self, session, report, case):
        job = session.scalar(
            select(Job)
            .where(Job.report_id == report.id)
            .order_by(Job.created_at.desc(), Job.id.desc())
            .limit(1)
        )
        request_id = job.request_id if job else None
        states = {
            a.stage: a.state
            for a in session.scalars(
                select(AnalysisRun)
                .where(AnalysisRun.request_id == request_id)
                .order_by(AnalysisRun.attempt)
            )
        }
        values = set(states.values())
        if "RUNNING" in values:
            state = "RUNNING"
        elif "PENDING" in values or not values:
            state = "PENDING"
        elif values <= {"SUCCEEDED", "NOT_APPLICABLE"}:
            state = "SUCCEEDED"
        elif "SUCCEEDED" in values or "PARTIAL" in values:
            state = "PARTIAL"
        elif values == {"CANCELLED"}:
            state = "CANCELLED"
        else:
            state = "FAILED"
        if job:
            state = "PENDING" if job.state == "RETRY_WAIT" else job.state
        return ProcessingRead(
            state=state,
            safe_reason="ANALYSIS_" + state,
            visual_state=states.get("VISUAL", "NOT_APPLICABLE"),
        )

    def media_projection(self, media):
        if media is None:
            return None
        state = (
            "EXPIRED"
            if media.expires_at <= self.clock() and media.state != "DELETED"
            else media.state
        )
        return MediaRead(id=media.id, state=state, expires_at=media.expires_at)

    def authority_detail(self, principal, case_id) -> AuthorityCaseDetail:
        with self.sessions.begin() as session:
            _, case, report = self._case(session, principal, case_id)
            return AuthorityCaseDetail(
                id=case.id,
                report_id=report.id,
                assigned_unit_id=case.assigned_unit_id,
                review_state=case.review_state,
                revision=case.revision,
                latest_evidence_version_id=case.latest_evidence_version_id,
                description=report.description,
                reported_location=Location(
                    latitude=report.reported_latitude, longitude=report.reported_longitude
                ),
                declared_capture_at=report.declared_capture_at,
                capture_time_basis=report.capture_time_basis,
                internal_notes=list(
                    session.scalars(
                        select(InternalNote.body).where(
                            InternalNote.case_id == case.id,
                            InternalNote.expires_at > self.clock(),
                            InternalNote.body.is_not(None),
                        )
                    )
                ),
                history=[
                    {
                        "revision": e.revision,
                        "action": e.action,
                        "evidence_version_id": str(e.evidence_version_id)
                        if e.evidence_version_id
                        else None,
                    }
                    for e in session.scalars(
                        select(ReviewEvent)
                        .where(ReviewEvent.case_id == case.id)
                        .order_by(ReviewEvent.revision)
                    )
                ],
            )

    def _event(self, session, user, case, expected_revision, action, *, reason=None, task_id=None):
        if case.revision != expected_revision:
            raise Conflict("Case changed; refresh before acting")
        case.revision += 1
        session.add(
            ReviewEvent(
                case_id=case.id,
                actor_user_id=user.id if user else None,
                unit_id=case.assigned_unit_id,
                revision=case.revision,
                action=action,
                evidence_version_id=case.latest_evidence_version_id,
                created_at=self.clock(),
                reason=reason,
                task_id=task_id,
            )
        )

    def review(self, principal, case_id, *, expected_revision: int, state: str):
        with self.sessions.begin() as session:
            user, case, _ = self._case(session, principal, case_id, lock=True)
            if case.revision != expected_revision:
                raise Conflict("Case changed; refresh before acting")
            if state not in TRANSITIONS[case.review_state]:
                raise ValueError("Invalid review transition")
            self._event(session, user, case, expected_revision, f"REVIEW_{state}")
            case.review_state = state
            return case.revision

    def add_internal_note(self, principal, case_id, *, expected_revision, body):
        if not isinstance(body, str) or not 1 <= len(body.strip()) <= 2000 or len(body) > 2000:
            raise ValueError("Internal note must contain 1–2000 characters")
        with self.sessions.begin() as session:
            user, case, report = self._case(session, principal, case_id, lock=True)
            self._event(session, user, case, expected_revision, "INTERNAL_NOTE_ADDED")
            note = InternalNote(
                case_id=case.id,
                author_id=user.id,
                body=body,
                created_at=self.clock(),
                expires_at=report.content_expires_at,
            )
            session.add(note)
            session.flush()
            return note.id

    def request_verification(self, principal, case_id, *, expected_revision, instructions):
        if (
            not isinstance(instructions, str)
            or not 1 <= len(instructions.strip()) <= 2000
            or len(instructions) > 2000
        ):
            raise ValueError("Verification instructions required, maximum 2000 characters")
        with self.sessions.begin() as session:
            user, case, report = self._case(session, principal, case_id, lock=True)
            if case.review_state == "CLOSED_NO_ACTION":
                raise Conflict("Reopen the case before requesting a follow-up")
            if report.withdrawn_at:
                raise Gone("Withdrawn reports cannot start a field follow-up")
            task = VerificationTask(
                case_id=case.id,
                requested_by=user.id,
                instructions=instructions,
                created_at=self.clock(),
                expires_at=report.content_expires_at,
            )
            session.add(task)
            session.flush()
            self._event(
                session,
                user,
                case,
                expected_revision,
                "VERIFICATION_REQUESTED",
                reason=instructions,
                task_id=task.id,
            )
            return task.id

    def request_refresh(self, principal, case_id, *, expected_revision):
        with self.sessions.begin() as session:
            user, case, report = self._case(session, principal, case_id, lock=True)
            if report.withdrawn_at:
                raise Gone("Report was withdrawn")
            self._event(session, user, case, expected_revision, "EVIDENCE_REFRESH_REQUESTED")
            charge(
                session,
                scope=case.id,
                rule="EVIDENCE_REFRESH",
                period="hour",
                maximum=self.limits.refreshes_per_hour,
            )
            media = session.scalar(
                select(Media).where(
                    Media.report_id == report.id,
                    Media.state == "ATTACHED",
                    Media.expires_at > self.clock(),
                )
            )
            return self._schedule(
                session,
                report,
                kind="REFRESH_EVIDENCE",
                has_media=bool(media),
                requested_by=user.id,
            )

    def append_evidence(
        self,
        principal,
        case_id,
        *,
        request_id: UUID,
        fragments: list[FragmentInput],
        manual_states=None,
        admission_token=None,
        worker_states=None,
    ):
        """Freeze normalized inputs; worker publication is fenced in this transaction.

        No Google/composite derived payload shape is accepted. Real normalized source
        retention remains disabled until source policy review. Tests explicitly inject
        synthetic permitted-source fixtures, not live provider responses.
        """
        if not self.provider_retention_reviewed and any(
            f.payload.kind != "retained_assessment_v1"
            or f.payload.reason_code != "NO_VISUAL_HYPOTHESIS"
            for f in fragments
        ):
            raise AccessDenied("Provider retention policy review required")
        if len(fragments) > 4 or not all(isinstance(f, FragmentInput) for f in fragments):
            raise ValueError("At most four validated normalized fragments required")
        if len({f.payload.kind for f in fragments}) != len(fragments):
            raise ValueError("Duplicate normalized source")
        now = self.clock()
        with self.sessions.begin() as session:
            user, case, report = self._case(session, principal, case_id, lock=True)
            if report.withdrawn_at:
                raise Gone("Report was withdrawn")
            if worker_states is not None:
                from app.processing.queue import WorkerLease

                if not isinstance(principal, WorkerLease):
                    raise AccessDenied("Worker lease required")
                manual_states = worker_states
            if manual_states is not None and worker_states is None:
                admission = session.scalar(
                    select(AnalysisAdmission)
                    .where(
                        AnalysisAdmission.case_id == case.id,
                        AnalysisAdmission.token == admission_token,
                        AnalysisAdmission.expires_at > now,
                    )
                    .with_for_update()
                )
                if admission is None:
                    raise Conflict("Manual request expired or was superseded")
            job = session.scalar(
                select(Job)
                .where(
                    Job.request_id == request_id,
                    Job.report_id == report.id,
                    Job.state == ("RUNNING" if manual_states is not None else "PENDING"),
                )
                .with_for_update()
            )
            if job is None or (worker_states is not None and job.id != principal.job_id):
                raise Conflict("Pending evidence request not found")
            if (
                manual_states is not None
                and worker_states is None
                and job.kind != "MANUAL_ENRICHMENT"
            ):
                raise Conflict("Explicit manual request required")
            if session.scalar(
                select(EvidenceVersion.id).where(EvidenceVersion.request_id == request_id)
            ):
                raise Conflict("Evidence request already finalized")
            deadlines = [report.content_expires_at]
            staged = []
            for fragment in fragments:
                if fragment.retrieved_at > now or (
                    fragment.observed_at and fragment.observed_at > fragment.retrieved_at
                ):
                    raise ValueError("Invalid source acquisition times")
                payload = fragment.payload.model_dump(mode="json")
                policy = POLICIES[payload["kind"]]
                source = policy.source
                expiry = min(
                    report.content_expires_at,
                    fragment.retrieved_at
                    + timedelta(days=min(policy.max_days, self.retention.source_days)),
                )
                if source == "GEMINI":
                    media = session.scalar(
                        select(Media).where(
                            Media.report_id == report.id,
                            Media.state == "ATTACHED",
                            Media.expires_at > now,
                        )
                    )
                    if media is None:
                        raise ValueError("Visual evidence requires unexpired attached media")
                    expiry = min(expiry, media.expires_at)
                if expiry <= now:
                    raise Gone("Source content has already expired")
                deadlines.append(expiry)
                staged.append((fragment, payload, source, expiry))
            case.evidence_sequence += 1
            version = EvidenceVersion(
                case_id=case.id,
                request_id=request_id,
                version=case.evidence_sequence,
                input_fingerprint=fingerprint(
                    {
                        "description": report.description,
                        "latitude": report.reported_latitude,
                        "longitude": report.reported_longitude,
                    }
                ),
                created_at=now,
                expires_at=min(deadlines),
            )
            session.add(version)
            session.flush()
            for fragment, payload, source, expiry in staged:
                if source == "RULES":
                    expiry = min(deadlines)
                session.add(
                    EvidenceFragment(
                        version_id=version.id,
                        source=source,
                        policy_version=POLICIES[payload["kind"]].version,
                        observed_at=fragment.observed_at,
                        retrieved_at=fragment.retrieved_at,
                        expires_at=expiry,
                        payload=payload,
                        content_sha256=fingerprint(payload),
                        state="AVAILABLE",
                    )
                )
            for source in ("GOOGLE_AQ", "GOOGLE_WEATHER", "GOOGLE_FORECAST"):
                session.add(
                    EvidenceFragment(
                        version_id=version.id,
                        source=source,
                        policy_version=GOOGLE_NO_STORE_POLICY,
                        retrieved_at=now,
                        expires_at=now,
                        payload=None,
                        content_sha256=None,
                        state="NOT_RETAINED_BY_POLICY",
                    )
                )
            if manual_states is not None:
                present = {source for _, _, source, _ in staged}
                for source in ("GEMINI", "NASA_FIRMS", "SENTINEL_5P", "RULES"):
                    if source not in present:
                        state = (
                            "NOT_RETAINED_BY_POLICY"
                            if not self.provider_retention_reviewed
                            else "UNAVAILABLE"
                        )
                        if source == "GEMINI" and manual_states["VISUAL"][0] == "NOT_APPLICABLE":
                            state = "NOT_APPLICABLE"
                        session.add(
                            EvidenceFragment(
                                version_id=version.id,
                                source=source,
                                policy_version="pilot_retained_sources_v1",
                                retrieved_at=now,
                                expires_at=now,
                                state=state,
                                payload=None,
                                content_sha256=None,
                            )
                        )
                for attempt in session.scalars(
                    select(AnalysisRun)
                    .where(AnalysisRun.request_id == request_id)
                    .with_for_update()
                ):
                    if worker_states is not None and attempt.attempt != job.attempts - 1:
                        continue
                    attempt.state, attempt.safe_reason = manual_states[attempt.stage]
                    attempt.ended_at = now
                job.state = (
                    "SUCCEEDED"
                    if any(v[0] == "SUCCEEDED" for v in manual_states.values())
                    else "FAILED"
                )
                if worker_states is not None:
                    values = {v[0] for v in worker_states.values()}
                    job.state = (
                        "SUCCEEDED"
                        if values <= {"SUCCEEDED", "NOT_APPLICABLE"}
                        else "PARTIAL"
                        if fragments
                        else "FAILED"
                    )
                    job.completed_at = now
                    job.safe_reason = (
                        "RETRY_EXHAUSTED" if job.attempts >= 3 and "FAILED" in values else None
                    )
                    job.lease_token = job.lease_expires_at = None
                else:
                    session.delete(admission)
            case.latest_evidence_version_id = version.id
            # Evidence arrival changes what a reviewer sees: invalidate stale revisions
            # and bind the audit event to the newly frozen version in this transaction.
            self._event(session, user, case, case.revision, "EVIDENCE_VERSION_ADDED")
            # Provider IO ran before this short publication transaction.
            return version.id

    def evidence(self, principal, case_id, version_id):
        with self.sessions.begin() as session:
            self._case(session, principal, case_id)
            version = session.scalar(
                select(EvidenceVersion).where(
                    EvidenceVersion.id == version_id,
                    EvidenceVersion.case_id == case_id,
                )
            )
            if version is None:
                raise NotFound("Evidence not found")
            fragments = []
            for f in session.scalars(
                select(EvidenceFragment)
                .where(EvidenceFragment.version_id == version.id)
                .order_by(EvidenceFragment.source)
            ):
                expired = f.state == "AVAILABLE" and f.expires_at <= self.clock()
                fragments.append(
                    {
                        "id": str(f.id),
                        "source": f.source,
                        "policy_version": f.policy_version,
                        "state": "EXPIRED_BY_SOURCE_POLICY" if expired else f.state,
                        "payload": f.payload if not expired and f.state == "AVAILABLE" else None,
                        "expires_at": f.expires_at.isoformat(),
                        "observed_at": f.observed_at.isoformat() if f.observed_at else None,
                        "retrieved_at": f.retrieved_at.isoformat(),
                        "attribution": next(
                            (
                                p.attribution
                                for p in POLICIES.values()
                                if p.version == f.policy_version
                            ),
                            "Content not retained under pilot policy",
                        ),
                    }
                )
            return {
                "id": str(version.id),
                "version": version.version,
                "input_policy": version.input_policy,
                "created_at": version.created_at.isoformat(),
                "expires_at": version.expires_at.isoformat(),
                "fragments": fragments,
            }

    def delete_report(self, principal, report_id):
        """Durable immediate suppression; maintenance purges bytes and records completion."""
        with self.sessions.begin() as session:
            _, report = self._owned_report(session, principal, report_id, lock=True)
            now = self.clock()
            report.deletion_state = "SUPPRESSED"
            session.add(
                PrivacyRequest(
                    report_id=report.id,
                    requested_at=now,
                    purge_due_at=min(now + timedelta(hours=24), report.content_expires_at),
                    ledger_expires_at=now + timedelta(days=self.retention.audit_days),
                )
            )
            report.audit_expires_at = max(
                report.audit_expires_at, now + timedelta(days=self.retention.audit_days)
            )
            for job in session.scalars(select(Job).where(Job.report_id == report.id)):
                if job.state in {"PENDING", "RUNNING", "RETRY_WAIT"}:
                    job.state = "CANCELLED"
                    job.lease_token = job.lease_expires_at = None
            for attempt in session.scalars(
                select(AnalysisRun).where(
                    AnalysisRun.report_id == report.id,
                    AnalysisRun.state.in_(["PENDING", "RUNNING"]),
                )
            ):
                attempt.state, attempt.ended_at = "CANCELLED", now
