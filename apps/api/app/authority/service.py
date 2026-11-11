from sqlalchemy import func, select

from app.authority.contracts import AuthorityPacket, AuthorityWorkspace, FieldRead
from app.persistence.contracts import AccessDenied, Conflict, NotFound
from app.persistence.models import (
    AnalysisRun,
    EvidenceFragment,
    EvidenceVersion,
    Identity,
    InformationRequest,
    InternalNote,
    Job,
    Media,
    Membership,
    ReporterUpdate,
    ReportSupplement,
    ReviewEvent,
    VerificationTask,
)
from app.persistence.policies import POLICIES
from app.persistence.repository import TRANSITIONS, fingerprint


class AuthorityService:
    def __init__(self, access):
        self.access, self.repo = access, access.repo

    def _member(self, session, unit_id, membership_id):
        member = session.scalar(
            select(Membership)
            .join(Identity, Identity.id == Membership.user_id)
            .where(
                Membership.id == membership_id,
                Membership.unit_id == unit_id,
                Membership.state == "ACTIVE",
                Membership.approved_at.is_not(None),
                Membership.approved_by.is_not(None),
                Identity.active.is_(True),
            )
            .with_for_update(of=[Membership, Identity], read=True)
        )
        if member is None:
            raise NotFound("Active unit member not found")
        return member

    @staticmethod
    def _member_id(session, unit_id, user_id):
        if user_id is None:
            return None
        return session.scalar(
            select(Membership.id).where(
                Membership.unit_id == unit_id, Membership.user_id == user_id
            )
        )

    def detail(self, principal, case_id):
        repo = self.repo
        with repo.sessions.begin() as session:
            user, case, report = repo._case(session, principal, case_id)
            now = repo.clock()

            def rows(table, order, maximum=50):
                return session.scalars(
                    select(table).where(table.case_id == case.id).order_by(order).limit(maximum)
                ).all()

            updates = session.scalars(
                select(ReporterUpdate)
                .where(ReporterUpdate.case_id == case.id)
                .order_by(
                    ReporterUpdate.published_at.desc(),
                    ReporterUpdate.case_revision.desc().nullslast(),
                    ReporterUpdate.id,
                )
                .limit(50)
            ).all()
            updates = [u for u in updates if u.expires_at > now]
            tasks = rows(VerificationTask, VerificationTask.created_at.desc())
            versions = rows(EvidenceVersion, EvidenceVersion.version.desc())
            jobs = session.execute(
                select(AnalysisRun, Job.created_at)
                .join(Job, Job.request_id == AnalysisRun.request_id)
                .where(AnalysisRun.report_id == report.id)
                .order_by(Job.created_at.desc(), AnalysisRun.attempt.desc(), AnalysisRun.stage)
                .limit(200)
            ).all()
            supplements = session.scalars(
                select(ReportSupplement)
                .where(ReportSupplement.report_id == report.id, ReportSupplement.expires_at > now)
                .order_by(
                    ReportSupplement.accepted_at.desc(),
                    ReportSupplement.case_revision.desc().nullslast(),
                )
                .limit(50)
            ).all()[::-1]
            media = session.scalar(select(Media).where(Media.report_id == report.id))
            allowed = (
                sorted(TRANSITIONS[case.review_state])
                if case.review_state != "CLOSED_NO_ACTION"
                else ["REOPEN"]
            )
            return AuthorityWorkspace(
                id=case.id,
                report_id=report.id,
                receipt_id=report.receipt_id,
                accepted_at=report.accepted_at,
                assigned_unit_id=case.assigned_unit_id,
                assigned_member_id=self._member_id(
                    session, case.assigned_unit_id, case.assigned_reviewer_id
                ),
                review_state=case.review_state,
                revision=case.revision,
                permitted_review_states=allowed,
                latest_evidence_version_id=case.latest_evidence_version_id,
                description=report.description,
                reported_place=report.reported_place,
                declared_category=report.declared_category,
                reported_location={
                    "latitude": report.reported_latitude,
                    "longitude": report.reported_longitude,
                },
                declared_capture_at=report.declared_capture_at,
                capture_time_basis=report.capture_time_basis,
                withdrawn_at=report.withdrawn_at,
                content_expires_at=report.content_expires_at,
                media=repo.media_projection(media) if not report.withdrawn_at else None,
                external_reference=case.external_reference,
                internal_notes=[
                    n.body
                    for n in rows(InternalNote, InternalNote.created_at.desc())
                    if n.body and n.expires_at > now
                ],
                history=self._history_rows(session, case.id),
                processing_attempts=[
                    {
                        "request_id": a.request_id,
                        "stage": a.stage,
                        "state": a.state,
                        "safe_reason": a.safe_reason,
                        "started_at": a.started_at,
                        "ended_at": a.ended_at,
                        "request_created_at": created,
                    }
                    for a, created in jobs
                ],
                evidence_versions=[
                    {
                        "id": v.id,
                        "version": v.version,
                        "created_at": v.created_at,
                        "expires_at": v.expires_at,
                        "input_policy": v.input_policy,
                    }
                    for v in versions
                ],
                field_follow_ups=[
                    FieldRead(
                        id=t.id,
                        state=t.state,
                        assigned_member_id=self._member_id(
                            session, case.assigned_unit_id, t.assigned_to
                        ),
                        instructions=t.instructions,
                        outcome=t.outcome,
                        created_at=t.created_at,
                        completed_at=t.completed_at,
                        revision=t.revision,
                    )
                    for t in tasks
                    if t.expires_at > now
                ],
                published_updates=[
                    {
                        "id": u.id,
                        "status": u.status,
                        "message": u.message,
                        "published_at": u.published_at,
                    }
                    for u in reversed(updates)
                ],
                information_requests=[
                    {
                        "id": r.id,
                        "state": r.state,
                        "prompt": r.prompt,
                        "created_at": r.created_at,
                        "expires_at": r.expires_at,
                    }
                    for r in rows(InformationRequest, InformationRequest.created_at.desc())
                    if r.expires_at > now
                ],
                supplements=[
                    {
                        "id": s.id,
                        "request_id": s.request_id,
                        "body": s.body,
                        "accepted_at": s.accepted_at,
                        "media": repo.media_projection(
                            session.scalar(select(Media).where(Media.supplement_id == s.id))
                        )
                        if not report.withdrawn_at
                        else None,
                    }
                    for s in supplements
                ],
            )

    @staticmethod
    def _history_rows(session, case_id, before=None, limit=50):
        query = select(ReviewEvent).where(ReviewEvent.case_id == case_id)
        if before is not None:
            query = query.where(ReviewEvent.revision < before)
        return [
            {
                "revision": e.revision,
                "action": e.action,
                "reason": e.reason,
                "created_at": e.created_at.isoformat(),
                "evidence_version_id": str(e.evidence_version_id)
                if e.evidence_version_id
                else None,
                "task_id": str(e.task_id) if e.task_id else None,
            }
            for e in session.scalars(query.order_by(ReviewEvent.revision.desc()).limit(limit))
        ]

    def history(self, principal, case_id, before=None):
        with self.repo.sessions.begin() as session:
            self.repo._case(session, principal, case_id)
            return self._history_rows(session, case_id, before)

    def review(self, principal, case_id, command):
        with self.repo.sessions.begin() as session:
            user, case, _ = self.repo._case(session, principal, case_id, lock=True)
            if case.revision != command.expected_revision:
                raise Conflict("Case changed; refresh before acting")
            target = command.state
            if target == "REOPEN":
                if case.review_state != "CLOSED_NO_ACTION":
                    raise ValueError("Only a closed case can reopen")
                target = "UNDER_REVIEW"
            elif target not in TRANSITIONS[case.review_state]:
                raise ValueError("Invalid transition")
            reason = command.reason.strip() if command.reason else None
            if command.state in {"CLOSED_NO_ACTION", "REOPEN"} and not reason:
                raise ValueError("Closure/reopening requires a reason")
            if target == "CLOSED_NO_ACTION" and session.scalar(
                select(VerificationTask.id)
                .where(
                    VerificationTask.case_id == case.id,
                    VerificationTask.state.in_(["REQUESTED", "ASSIGNED"]),
                )
                .limit(1)
            ):
                raise Conflict("Complete or cancel open field follow-ups before closure")
            self.repo._event(
                session,
                user,
                case,
                command.expected_revision,
                "REVIEW_" + command.state,
                reason=reason,
            )
            case.review_state = target
            if target == "CLOSED_NO_ACTION":
                for request in session.scalars(
                    select(InformationRequest)
                    .where(
                        InformationRequest.case_id == case.id, InformationRequest.state == "OPEN"
                    )
                    .with_for_update()
                ):
                    request.state = "CLOSED"
            return case.revision

    def assign(self, principal, case_id, command):
        with self.repo.sessions.begin() as session:
            user, case, _ = self.repo._case(session, principal, case_id, lock=True)
            _, actor = self.access._unit(session, principal, case.assigned_unit_id, lock=True)
            if command.claim_self and command.membership_id:
                raise ValueError("Choose a self-claim or an explicit assignee")
            if command.claim_self:
                command = command.model_copy(update={"membership_id": actor.id})
            target = (
                self._member(session, case.assigned_unit_id, command.membership_id)
                if command.membership_id
                else None
            )
            if actor.role != "UNIT_ADMIN" and (target is None or target.user_id != user.id):
                raise AccessDenied(
                    "Only a unit administrator may assign another reviewer or clear ownership"
                )
            if actor.role != "UNIT_ADMIN" and case.assigned_reviewer_id not in {None, user.id}:
                raise AccessDenied("Another reviewer owns this case; ask the unit administrator")
            self.repo._event(session, user, case, command.expected_revision, "CASE_ASSIGNED")
            case.assigned_reviewer_id = target.user_id if target else None
            return case.revision

    def publish(self, principal, case_id, command):
        with self.repo.sessions.begin() as session:
            user, case, report = self.repo._case(session, principal, case_id, lock=True)
            if command.status == "CLOSED" and case.review_state != "CLOSED_NO_ACTION":
                raise ValueError("Close the internal review before publishing closure")
            self.repo._event(
                session, user, case, command.expected_revision, "REPORTER_UPDATE_PUBLISHED"
            )
            session.add(
                ReporterUpdate(
                    case_id=case.id,
                    publisher_id=user.id,
                    status=command.status,
                    message=command.message,
                    published_at=self.repo.clock(),
                    case_revision=case.revision,
                    expires_at=report.content_expires_at,
                )
            )
            return case.revision

    def reference(self, principal, case_id, command):
        with self.repo.sessions.begin() as session:
            user, case, _ = self.repo._case(session, principal, case_id, lock=True)
            if not command.reference.strip():
                raise ValueError("Reference is required")
            self.repo._event(
                session,
                user,
                case,
                command.expected_revision,
                "EXTERNAL_REFERENCE_RECORDED",
                reason=command.reference,
            )
            case.external_reference = command.reference
            return case.revision

    def field_event(self, principal, case_id, task_id, command):
        with self.repo.sessions.begin() as session:
            user, case, _ = self.repo._case(session, principal, case_id, lock=True)
            _, actor = self.access._unit(session, principal, case.assigned_unit_id, lock=True)
            task = session.scalar(
                select(VerificationTask)
                .where(
                    VerificationTask.id == task_id,
                    VerificationTask.case_id == case.id,
                    VerificationTask.expires_at > self.repo.clock(),
                )
                .with_for_update()
            )
            if task is None:
                raise NotFound("Field follow-up not found")
            if command.action != "ASSIGN" and command.membership_id is not None:
                raise ValueError("Only assignment accepts a target membership")
            if command.action in {"CLAIM", "ASSIGN"}:
                if task.state not in {"REQUESTED", "ASSIGNED"}:
                    raise Conflict("Follow-up is terminal")
                if command.action == "CLAIM":
                    if task.assigned_to not in {None, user.id}:
                        raise AccessDenied("Follow-up belongs to another reviewer")
                    target = user.id
                else:
                    if actor.role != "UNIT_ADMIN":
                        raise AccessDenied("Unit administrator required")
                    target = self._member(
                        session, case.assigned_unit_id, command.membership_id
                    ).user_id
                task.assigned_to, task.state = target, "ASSIGNED"
            elif command.action == "COMPLETE":
                if task.state != "ASSIGNED":
                    raise Conflict("Claim or assign before completing")
                if actor.role != "UNIT_ADMIN" and task.assigned_to != user.id:
                    raise AccessDenied("Assignee required")
                task.state, task.outcome, task.completed_at = (
                    "COMPLETED",
                    command.reason,
                    self.repo.clock(),
                )
            else:
                if task.state not in {"REQUESTED", "ASSIGNED"}:
                    raise Conflict("Follow-up is terminal")
                if actor.role != "UNIT_ADMIN" and user.id not in {
                    task.assigned_to,
                    task.requested_by,
                }:
                    raise AccessDenied("Task requester or assignee required")
                task.state = "CANCELLED"
            self.repo._event(
                session,
                user,
                case,
                command.expected_revision,
                "FIELD_" + command.action,
                reason=command.reason,
                task_id=task.id,
            )
            task.revision += 1
            return case.revision

    def packet(self, principal, case_id):
        with self.repo.sessions.begin() as session:
            _, case, _ = self.repo._case(session, principal, case_id)
            versions = session.scalars(
                select(EvidenceVersion)
                .where(EvidenceVersion.case_id == case.id)
                .order_by(EvidenceVersion.version.desc())
                .limit(100)
            ).all()
            payload = {
                "case_id": str(case.id),
                "review_state": case.review_state,
                "revision": case.revision,
                "created_at": case.created_at.isoformat(),
                "input_policy": "pilot_retained_sources_v1",
                "review_events": [
                    {
                        "revision": e.revision,
                        "action": e.action,
                        "created_at": e.created_at.isoformat(),
                        "evidence_version_id": str(e.evidence_version_id)
                        if e.evidence_version_id
                        else None,
                    }
                    for e in session.scalars(
                        select(ReviewEvent)
                        .where(ReviewEvent.case_id == case.id)
                        .order_by(ReviewEvent.revision.desc())
                        .limit(500)
                    )
                ],
                "evidence_versions": [],
            }
            for v in reversed(versions):
                fragments = []
                for f in session.scalars(
                    select(EvidenceFragment)
                    .where(EvidenceFragment.version_id == v.id)
                    .order_by(EvidenceFragment.source)
                ):
                    policy = next(
                        (p for p in POLICIES.values() if p.version == f.policy_version), None
                    )
                    fragments.append(
                        {
                            "source": f.source,
                            "policy_version": f.policy_version,
                            "observed_at": f.observed_at.isoformat() if f.observed_at else None,
                            "retrieved_at": f.retrieved_at.isoformat(),
                            "expires_at": f.expires_at.isoformat(),
                            "state": "EXPIRED_BY_SOURCE_POLICY"
                            if f.state == "AVAILABLE" and f.expires_at <= self.repo.clock()
                            else f.state,
                            "content": "OMITTED_BY_EXPORT_POLICY",
                            "attribution": policy.attribution
                            if policy
                            else "Google Maps Platform; content not retained",
                        }
                    )
                payload["evidence_versions"].append(
                    {
                        "id": str(v.id),
                        "version": v.version,
                        "created_at": v.created_at.isoformat(),
                        "input_policy": v.input_policy,
                        "fragments": fragments,
                    }
                )
            payload["review_events"].reverse()
            version_count = session.scalar(
                select(func.count())
                .select_from(EvidenceVersion)
                .where(EvidenceVersion.case_id == case.id)
            )
            event_count = session.scalar(
                select(func.count()).select_from(ReviewEvent).where(ReviewEvent.case_id == case.id)
            )
            payload["limits"] = {
                "versions": 100,
                "events": 500,
                "total_versions": version_count,
                "total_events": event_count,
                "truncated": version_count > 100 or event_count > 500,
                "ordering": "most recent entries, in chronological order",
            }
            return AuthorityPacket(
                created_at=self.repo.clock(), packet=payload, sha256=fingerprint(payload)
            )
