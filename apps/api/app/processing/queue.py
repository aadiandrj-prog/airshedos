"""Short transactions only. A lease is an internal capability, never an API identity."""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select

from app.access.limits import charge
from app.persistence.contracts import Conflict, Gone, NotFound, PersistenceError
from app.persistence.models import (
    AnalysisRun,
    Case,
    Identity,
    Job,
    MaintenanceHeartbeat,
    Media,
    Membership,
    ProcessingMetric,
    Report,
    Unit,
)

ACTIVE = ("PENDING", "RUNNING", "RETRY_WAIT")


@dataclass(frozen=True)
class WorkerLease:
    job_id: UUID
    token: UUID


def guarded_case(repo, session, lease, case_id, *, lock=False):
    if repo.release_epoch is not None:
        from app.operations.readiness import require_released

        require_released(session, repo.release_epoch)
    # Lock order matches withdrawal, retention and human review: report -> case -> job.
    job = session.get(Job, lease.job_id)
    if job is None:
        raise Conflict("Worker lease lost")
    report = session.scalar(select(Report).where(Report.id == job.report_id).with_for_update())
    case = session.scalar(select(Case).where(Case.report_id == report.id).with_for_update())
    job = session.scalar(
        select(Job)
        .where(Job.id == lease.job_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    now = session.scalar(select(func.clock_timestamp()))
    if (
        case.id != case_id
        or job.state != "RUNNING"
        or job.lease_token != lease.token
        or job.lease_expires_at is None
        or job.lease_expires_at <= now
    ):
        raise Conflict("Worker lease lost")
    if report.deletion_state != "ACTIVE" or report.content_expires_at <= now or report.withdrawn_at:
        raise Gone("Report unavailable for processing")
    owner = session.scalar(
        select(Identity).where(Identity.id == report.reporter_user_id).with_for_update(read=True)
    )
    unit = session.scalar(
        select(Unit).where(Unit.id == case.assigned_unit_id).with_for_update(read=True)
    )
    if (
        owner is None
        or not owner.active
        or unit is None
        or unit.is_prototype
        or unit.approved_at is None
        or job.authorized_unit_id != unit.id
    ):
        raise NotFound("Authorised processing scope unavailable")
    actor = None
    if job.requested_by:
        actor = session.scalar(
            select(Identity).where(Identity.id == job.requested_by).with_for_update(read=True)
        )
        member = session.scalar(
            select(Membership)
            .where(
                Membership.user_id == job.requested_by,
                Membership.unit_id == unit.id,
                Membership.state == "ACTIVE",
                Membership.approved_by.is_not(None),
                Membership.approved_at.is_not(None),
            )
            .with_for_update(read=True)
        )
        if actor is None or not actor.active or member is None:
            raise NotFound("Authorised processing scope unavailable")
    return actor, case, report


class DurableQueue:
    def __init__(self, repo, *, lease_seconds=120, backoff=(30, 120)):
        if (
            not 1 <= lease_seconds <= 600
            or len(backoff) != 2
            or any(x < 0 or x > 3600 for x in backoff)
        ):
            raise ValueError("Invalid bounded worker timing")
        self.repo, self.lease_seconds, self.backoff = repo, lease_seconds, backoff

    def claim(self, *, report_id=None):
        with self.repo.sessions.begin() as session:
            if self.repo.release_epoch is not None:
                from app.operations.readiness import require_released

                require_released(session, self.repo.release_epoch)
            now = session.scalar(select(func.clock_timestamp()))
            query = select(Job).where(Job.kind.in_(["PROCESS_REPORT", "REFRESH_EVIDENCE"]))
            if report_id is not None:
                query = query.where(Job.report_id == report_id)
            job = session.scalar(
                query.where(
                    or_(
                        Job.state.in_(["PENDING", "RETRY_WAIT"])
                        & or_(Job.next_run_at.is_(None), Job.next_run_at <= now),
                        (Job.state == "RUNNING") & (Job.lease_expires_at <= now),
                    )
                )
                .order_by(Job.created_at, Job.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if job is None:
                return None
            if job.attempts >= 3:
                job.state, job.safe_reason, job.completed_at = "FAILED", "RETRY_EXHAUSTED", now
                job.lease_token = job.lease_expires_at = None
                for a in session.scalars(
                    select(AnalysisRun).where(AnalysisRun.request_id == job.request_id)
                ):
                    if a.state in ("PENDING", "RUNNING"):
                        a.state, a.safe_reason, a.ended_at = "FAILED", "RETRY_EXHAUSTED", now
                return None
            job.attempts += 1
            job.state, job.lease_token = "RUNNING", uuid4()
            job.heartbeat_at = now
            job.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
            # Stage rows describe this attempt; no provider payload is stored in the queue.
            rows = session.scalars(
                select(AnalysisRun)
                .where(AnalysisRun.request_id == job.request_id)
                .order_by(AnalysisRun.attempt)
            ).all()
            for a in rows:
                if a.state == "RUNNING":
                    a.state, a.safe_reason, a.ended_at = "FAILED", "LEASE_EXPIRED", now
            for stage in ("VISUAL", "ENVIRONMENT", "CORROBORATION", "FORECAST"):
                a = next(
                    (r for r in rows if r.stage == stage and r.attempt == job.attempts - 1), None
                )
                if a is None:
                    a = AnalysisRun(
                        report_id=job.report_id,
                        request_id=job.request_id,
                        stage=stage,
                        attempt=job.attempts - 1,
                        state="PENDING",
                    )
                    session.add(a)
                prior = next(
                    (r for r in rows if r.stage == stage and r.state == "NOT_APPLICABLE"), None
                )
                if stage == "FORECAST" or prior is not None:
                    a.state, a.safe_reason, a.ended_at = (
                        "NOT_APPLICABLE",
                        "NOT_RETAINED_BY_POLICY" if stage == "FORECAST" else prior.safe_reason,
                        now,
                    )
                else:
                    a.state, a.started_at, a.ended_at = "RUNNING", now, None
            return WorkerLease(job.id, job.lease_token)

    def snapshot(self, lease):
        with self.repo.sessions.begin() as session:
            job = session.get(Job, lease.job_id)
            case_id = session.scalar(select(Case.id).where(Case.report_id == job.report_id))
            _, case, report = guarded_case(self.repo, session, lease, case_id)
            media = session.scalar(
                select(Media).where(
                    Media.report_id == report.id,
                    Media.state == "ATTACHED",
                    Media.expires_at > func.clock_timestamp(),
                )
            )
            return case.id, dict(
                request_id=job.request_id,
                report_id=report.id,
                media_id=media.id if media else None,
                latitude=report.reported_latitude,
                longitude=report.reported_longitude,
                description=report.description,
                accepted_at=report.accepted_at,
                approved=self.repo.provider_retention_reviewed,
            )

    def heartbeat(self, lease, case_id):
        with self.repo.sessions.begin() as session:
            guarded_case(self.repo, session, lease, case_id)
            job = session.get(Job, lease.job_id)
            now = session.scalar(select(func.clock_timestamp()))
            job.heartbeat_at, job.lease_expires_at = (
                now,
                now + timedelta(seconds=self.lease_seconds),
            )

    def admit(self, lease, case_id, source, units):
        with self.repo.sessions.begin() as session:
            guarded_case(self.repo, session, lease, case_id)
            now = session.scalar(select(func.clock_timestamp()))
            if not self.repo.provider_retention_reviewed:
                raise PersistenceError("Provider retention policy review required")
            if self.repo.require_maintenance:
                h = session.get(MaintenanceHeartbeat, "retention")
                if h is None or h.succeeded_at < now - timedelta(seconds=120):
                    raise PersistenceError("Retention maintenance required")
            for _ in range(units):
                charge(
                    session,
                    scope="global",
                    rule="PAID_ANALYSIS",
                    period="day",
                    maximum=self.repo.limits.provider_calls_per_day,
                )
            session.add(
                ProcessingMetric(
                    job_id=lease.job_id,
                    source=source,
                    outcome="ADMITTED",
                    duration_ms=0,
                    usage_units=units,
                    created_at=now,
                    expires_at=now + timedelta(days=30),
                )
            )

    def metric(self, lease, source, outcome, duration_ms):
        with self.repo.sessions.begin() as session:
            job = session.get(Job, lease.job_id)
            if job is None or job.lease_token != lease.token or job.state != "RUNNING":
                return
            now = session.scalar(select(func.clock_timestamp()))
            session.add(
                ProcessingMetric(
                    job_id=job.id,
                    source=source,
                    outcome=outcome,
                    duration_ms=max(0, round(duration_ms)),
                    usage_units=0,
                    created_at=now,
                    expires_at=now + timedelta(days=30),
                )
            )

    def retry(self, lease, case_id, states):
        with self.repo.sessions.begin() as session:
            guarded_case(self.repo, session, lease, case_id)
            job = session.get(Job, lease.job_id)
            if job.attempts >= 3:
                return False
            now = session.scalar(select(func.clock_timestamp()))
            for a in session.scalars(
                select(AnalysisRun).where(
                    AnalysisRun.request_id == job.request_id,
                    AnalysisRun.attempt == job.attempts - 1,
                )
            ):
                a.state, a.safe_reason = states[a.stage]
                a.ended_at = now
            job.state, job.safe_reason = "RETRY_WAIT", "TRANSIENT_PROVIDER_FAILURE"
            job.next_run_at = now + timedelta(seconds=self.backoff[job.attempts - 1])
            job.lease_token = job.lease_expires_at = None
            return True

    def stop(self, lease, reason, *, cancelled=False):
        # Best-effort terminal control; never touches a successor's lease or result.
        with self.repo.sessions.begin() as session:
            job = session.scalar(select(Job).where(Job.id == lease.job_id).with_for_update())
            if job is None or job.lease_token != lease.token or job.state != "RUNNING":
                return
            now = session.scalar(select(func.clock_timestamp()))
            job.state = "CANCELLED" if cancelled else "FAILED"
            job.safe_reason, job.completed_at = reason, now
            job.lease_token = job.lease_expires_at = None
            for a in session.scalars(
                select(AnalysisRun).where(AnalysisRun.request_id == job.request_id)
            ):
                if a.state in ("RUNNING", "PENDING"):
                    a.state, a.safe_reason, a.ended_at = job.state, reason, now


def enqueue_refresh(repo, principal, case_id, command):
    from app.authority.contracts import EnrichmentRead

    with repo.sessions.begin() as session:
        user, case, report = repo._case(session, principal, case_id, lock=True)
        if report.withdrawn_at:
            raise Gone("Report withdrawn; processing stopped")
        if case.review_state == "CLOSED_NO_ACTION":
            raise Conflict("Reopen before enrichment")
        # Serialised by the case lock: double clicks/reloads join a current logical run.
        active = session.scalar(
            select(Job)
            .where(Job.report_id == report.id, Job.state.in_(ACTIVE))
            .order_by(Job.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        if active:
            return EnrichmentRead(request_id=active.request_id, version_id=None, state=active.state)
        repo._event(
            session,
            user,
            case,
            command.expected_revision,
            "EVIDENCE_REFRESH_REQUESTED",
            reason=command.reason,
        )
        charge(
            session,
            scope=case.id,
            rule="EVIDENCE_REFRESH",
            period="hour",
            maximum=repo.limits.refreshes_per_hour,
        )
        media = session.scalar(
            select(Media.id).where(
                Media.report_id == report.id,
                Media.state == "ATTACHED",
                Media.expires_at > repo.clock(),
            )
        )
        request_id = repo._schedule(
            session, report, kind="REFRESH_EVIDENCE", has_media=bool(media), requested_by=user.id
        )
        return EnrichmentRead(request_id=request_id, version_id=None, state="PENDING")
