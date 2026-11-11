import hashlib
from datetime import UTC, timedelta

from sqlalchemy import select, text

from app.access.limits import charge
from app.persistence.contracts import Conflict, Gone, NotFound
from app.persistence.models import (
    Case,
    IdempotencyKey,
    InformationRequest,
    Media,
    ReporterUpdate,
    ReportSupplement,
)
from app.persistence.repository import fingerprint
from app.resident.contracts import ResidentReceipt, SupplementReceipt


def lock_key(session, user_id, operation, key):
    value = int.from_bytes(
        hashlib.sha256(f"{user_id}:{operation}:{key}".encode()).digest()[:8], signed=True
    )
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": value})


class ResidentService:
    def __init__(self, repository):
        self.repo = repository

    def accept(self, principal, body, key, created_at):
        accepted = self.repo.create_report(principal, body, key=key, key_created_at=created_at)
        return ResidentReceipt(
            report_id=accepted.report_id,
            receipt_id=accepted.receipt_id,
            accepted_at=accepted.accepted_at,
            replayed=accepted.replayed,
        )

    def submission(self, principal, key):
        """Authenticated owner lookup for uncertain network outcomes; no bearer receipt link."""
        with self.repo.sessions.begin() as session:
            user = self.repo.identity(session, principal, lock=True)
            lock_key(session, user.id, "CREATE_REPORT", key)
            prior = session.scalar(
                select(IdempotencyKey).where(
                    IdempotencyKey.principal_id == user.id,
                    IdempotencyKey.operation == "CREATE_REPORT",
                    IdempotencyKey.key == key,
                )
            )
            if prior is None:
                raise NotFound("Committed submission not found")
            _, report = self.repo._owned_report(session, principal, prior.report_id)
            if prior.tombstone:
                raise Gone("Submission no longer available")
            return ResidentReceipt(
                report_id=report.id,
                receipt_id=report.receipt_id,
                accepted_at=report.accepted_at,
                replayed=True,
            )

    def request_information(self, principal, case_id, *, expected_revision, prompt):
        """Deliberate reviewer publication seam; no Phase 3 reviewer UI/HTTP action."""
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 1000:
            raise ValueError("Published request must contain 1–1000 characters")
        with self.repo.sessions.begin() as session:
            user, case, report = self.repo._case(session, principal, case_id, lock=True)
            if case.review_state == "CLOSED_NO_ACTION":
                raise Conflict("Reopen the case before requesting information")
            if report.withdrawn_at:
                raise Gone("Withdrawn reports cannot start a new information request")
            self.repo._event(
                session, user, case, expected_revision, "INFORMATION_REQUEST_PUBLISHED"
            )
            update = ReporterUpdate(
                case_id=case.id,
                publisher_id=user.id,
                status="UPDATE_AVAILABLE",
                message=prompt,
                published_at=self.repo.clock(),
                case_revision=case.revision,
                expires_at=report.content_expires_at,
            )
            session.add(update)
            session.flush()
            request = InformationRequest(
                case_id=case.id,
                update_id=update.id,
                prompt=prompt,
                created_at=self.repo.clock(),
                expires_at=report.content_expires_at,
            )
            session.add(request)
            session.flush()
            return request.id

    def reply(self, principal, report_id, request_id, body, key, created_at):
        digest = fingerprint(
            body.model_dump(mode="json")
            | {
                "report_id": str(report_id),
                "request_id": str(request_id),
                "key_created_at": created_at.astimezone(UTC).isoformat(),
            }
        )
        with self.repo.sessions.begin() as session:
            user, report = self.repo._owned_report(session, principal, report_id, lock=True)
            lock_key(session, user.id, "REPLY_INFORMATION", key)
            now = self.repo.clock()
            prior = session.scalar(
                select(IdempotencyKey).where(
                    IdempotencyKey.principal_id == user.id,
                    IdempotencyKey.operation == "REPLY_INFORMATION",
                    IdempotencyKey.key == key,
                )
            )
            if prior:
                if prior.tombstone:
                    raise Gone("Reply no longer available")
                if prior.fingerprint != digest or prior.report_id != report.id:
                    raise Conflict("Retry input differs from accepted reply")
                supplement = session.get(ReportSupplement, prior.result_id)
                return self._reply_receipt(supplement, replayed=True)
            if created_at < now - timedelta(hours=24):
                raise Gone("New reply key is too old")
            if created_at > now + timedelta(seconds=60):
                raise ValueError("Reply creation time is in the future")
            case = session.scalar(select(Case).where(Case.report_id == report.id).with_for_update())
            request = session.scalar(
                select(InformationRequest)
                .where(
                    InformationRequest.id == request_id,
                    InformationRequest.case_id == case.id,
                    InformationRequest.expires_at > now,
                )
                .with_for_update()
            )
            if request is None:
                raise NotFound("Information request not found")
            if request.state != "OPEN":
                raise Conflict("Information request already answered or closed")
            charge(
                session,
                scope=user.id,
                rule="RESIDENT_REPLY",
                period="day",
                maximum=self.repo.limits.replies_per_day,
            )
            media = None
            if body.media_id:
                media = session.scalar(
                    select(Media)
                    .where(
                        Media.id == body.media_id,
                        Media.owner_id == user.id,
                        Media.state == "READY",
                        Media.expires_at > self.repo.clock(),
                    )
                    .with_for_update()
                )
                if media is None or media.report_id or media.supplement_id:
                    raise NotFound("Ready private media not found")
            supplement = ReportSupplement(
                report_id=report.id,
                request_id=request.id,
                author_id=user.id,
                body=body.body,
                accepted_at=now,
                case_revision=case.revision + 1,
                expires_at=report.content_expires_at,
            )
            session.add(supplement)
            session.flush()
            if media:
                media.supplement_id, media.state = supplement.id, "ATTACHED"
                media.expires_at = min(
                    report.content_expires_at,
                    media.created_at + timedelta(days=self.repo.retention.media_days),
                )
            request.state = "ANSWERED"
            self.repo._event(session, user, case, case.revision, "RESIDENT_SUPPLEMENT_RECEIVED")
            session.add(
                IdempotencyKey(
                    principal_id=user.id,
                    operation="REPLY_INFORMATION",
                    key=key,
                    key_created_at=created_at,
                    fingerprint=digest,
                    report_id=report.id,
                    result_id=supplement.id,
                    consumed_until=report.audit_expires_at,
                )
            )
            result = self._reply_receipt(supplement)
        return result

    @staticmethod
    def _reply_receipt(supplement, replayed=False):
        return SupplementReceipt(
            id=supplement.id,
            report_id=supplement.report_id,
            request_id=supplement.request_id,
            accepted_at=supplement.accepted_at,
            replayed=replayed,
        )
