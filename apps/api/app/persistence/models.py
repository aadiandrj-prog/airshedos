"""Relational custody. Protected payload columns are nullable only for explicit purge."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    MetaData,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )
    type_annotation_map = {datetime: DateTime(timezone=True), dict: JSONB(none_as_null=True)}


class Identity(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    issuer: Mapped[str] = mapped_column(String(512))
    subject: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime]
    lock_guard: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    __table_args__ = (UniqueConstraint("issuer", "subject"),)


class Unit(Base):
    __tablename__ = "units"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    approved_at: Mapped[datetime | None]
    is_prototype: Mapped[bool] = mapped_column(default=False)
    lock_guard: Mapped[int] = mapped_column(default=0, server_default=text("0"))


class Membership(Base):
    __tablename__ = "unit_memberships"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id"))
    role: Mapped[str] = mapped_column(String(20))
    state: Mapped[str] = mapped_column(String(20), default="PENDING")
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None]
    lock_guard: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    __table_args__ = (
        UniqueConstraint("user_id", "unit_id"),
        CheckConstraint("role IN ('REVIEWER','UNIT_ADMIN')", name="role"),
        CheckConstraint("state IN ('PENDING','ACTIVE','SUSPENDED','REVOKED')", name="state"),
        CheckConstraint(
            "state <> 'ACTIVE' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)",
            name="approval",
        ),
    )


class AuthSession(Base):
    """Metadata/sealed-token seam; Phase 2 owns managed session lifecycle and grants."""

    __tablename__ = "auth_sessions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    sdk_key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    binding_hash: Mapped[str] = mapped_column(String(64), unique=True)
    issuer: Mapped[str] = mapped_column(String(512))
    subject: Mapped[str] = mapped_column(String(255))
    idp_sid_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime]
    idle_expires_at: Mapped[datetime]
    absolute_expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    lock_guard: Mapped[int] = mapped_column(default=0, server_default=text("0"))


class AuthSessionSecret(Base):
    """Separate grants: API can read session metadata, never this encrypted SDK data."""

    __tablename__ = "auth_session_secrets"
    session_id: Mapped[UUID] = mapped_column(ForeignKey("auth_sessions.id"), primary_key=True)
    sealed_data: Mapped[bytes] = mapped_column(LargeBinary)


class OperatorGrant(Base):
    __tablename__ = "operator_grants"
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    active: Mapped[bool] = mapped_column(default=True)
    granted_at: Mapped[datetime]


class MembershipProposal(Base):
    __tablename__ = "membership_proposals"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    unit_id: Mapped[UUID] = mapped_column(ForeignKey("units.id"), index=True)
    target_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    proposed_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(20))
    state: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    __table_args__ = (
        CheckConstraint("role IN ('REVIEWER','UNIT_ADMIN')", name="role"),
        CheckConstraint("state IN ('PENDING','APPROVED','REJECTED')", name="state"),
    )


class AccessAudit(Base):
    __tablename__ = "access_audit"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    target_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    unit_id: Mapped[UUID | None] = mapped_column(ForeignKey("units.id"))
    action: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]


class AbuseWindow(Base):
    __tablename__ = "abuse_windows"
    scope: Mapped[str] = mapped_column(String(100), primary_key=True)
    rule: Mapped[str] = mapped_column(String(30), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(primary_key=True)
    used: Mapped[int] = mapped_column(default=0)
    expires_at: Mapped[datetime] = mapped_column(index=True)
    __table_args__ = (CheckConstraint("used >= 0", name="used"),)


class AnalysisAdmission(Base):
    __tablename__ = "analysis_admissions"
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id"), primary_key=True)
    token: Mapped[UUID] = mapped_column(default=uuid4)
    expires_at: Mapped[datetime] = mapped_column(index=True)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    reporter_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    receipt_id: Mapped[UUID] = mapped_column(unique=True, default=uuid4)
    accepted_at: Mapped[datetime]
    description: Mapped[str | None] = mapped_column(String(2000))
    reported_place: Mapped[str | None] = mapped_column(String(200))
    declared_category: Mapped[str | None] = mapped_column(String(30))
    reported_latitude: Mapped[float | None]
    reported_longitude: Mapped[float | None]
    declared_capture_at: Mapped[datetime | None]
    capture_time_basis: Mapped[str] = mapped_column(String(30))
    content_expires_at: Mapped[datetime] = mapped_column(index=True)
    audit_expires_at: Mapped[datetime] = mapped_column(index=True)
    withdrawn_at: Mapped[datetime | None]
    deletion_state: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    purged_at: Mapped[datetime | None]
    lock_guard: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    __table_args__ = (
        CheckConstraint(
            "deletion_state IN ('ACTIVE','SUPPRESSED','PURGED')", name="deletion_state"
        ),
        CheckConstraint(
            "description IS NULL OR length(btrim(description)) BETWEEN 1 AND 2000",
            name="description",
        ),
        CheckConstraint(
            "reported_latitude BETWEEN -90 AND 90 AND reported_longitude BETWEEN -180 AND 180",
            name="location",
        ),
        CheckConstraint(
            "capture_time_basis IN ('unknown','resident_declared')", name="capture_basis"
        ),
    )


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(ForeignKey("reports.id"), unique=True)
    assigned_unit_id: Mapped[UUID | None] = mapped_column(ForeignKey("units.id"), index=True)
    assigned_reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    review_state: Mapped[str] = mapped_column(String(30), default="NEW")
    revision: Mapped[int] = mapped_column(default=0)
    evidence_sequence: Mapped[int] = mapped_column(default=0)
    latest_evidence_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("evidence_versions.id", use_alter=True, name="fk_cases_latest_evidence")
    )
    created_at: Mapped[datetime]
    external_reference: Mapped[str | None] = mapped_column(String(200))
    __table_args__ = (
        CheckConstraint("revision >= 0 AND evidence_sequence >= 0", name="revision"),
        CheckConstraint(
            "review_state IN ('NEW','UNDER_REVIEW','ACKNOWLEDGED','MONITORING','CLOSED_NO_ACTION')",
            name="review_state",
        ),
    )


class Media(Base):
    __tablename__ = "media"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    report_id: Mapped[UUID | None] = mapped_column(ForeignKey("reports.id"), unique=True)
    supplement_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("report_supplements.id"), unique=True
    )
    object_key: Mapped[str | None] = mapped_column(String(32), unique=True)
    mime_type: Mapped[str] = mapped_column(String(30), default="image/jpeg")
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20), default="WRITING")
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime] = mapped_column(index=True)
    __table_args__ = (
        CheckConstraint("report_id IS NULL OR supplement_id IS NULL", name="one_parent"),
        CheckConstraint(
            "state IN ('WRITING','READY','ATTACHED','DELETING','DELETED')", name="state"
        ),
        CheckConstraint("size_bytes BETWEEN 1 AND 4000000", name="size"),
    )


class AnalysisRun(Base):
    __tablename__ = "processing_attempts"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(ForeignKey("reports.id"), index=True)
    request_id: Mapped[UUID]
    stage: Mapped[str] = mapped_column(String(30))
    attempt: Mapped[int] = mapped_column(default=0)
    state: Mapped[str] = mapped_column(String(30))
    safe_reason: Mapped[str | None] = mapped_column(String(50))
    started_at: Mapped[datetime | None]
    ended_at: Mapped[datetime | None]
    __table_args__ = (
        UniqueConstraint("request_id", "stage", "attempt"),
        CheckConstraint(
            "stage IN ('VISUAL','ENVIRONMENT','CORROBORATION','FORECAST')", name="stage"
        ),
        CheckConstraint("attempt BETWEEN 0 AND 3", name="attempt"),
        CheckConstraint(
            "state IN ('PENDING','RUNNING','SUCCEEDED','PARTIAL','FAILED',"
            "'NOT_APPLICABLE','CANCELLED')",
            name="state",
        ),
    )


class EvidenceVersion(Base):
    __tablename__ = "evidence_versions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id"), index=True)
    request_id: Mapped[UUID] = mapped_column(unique=True)
    version: Mapped[int]
    input_fingerprint: Mapped[str | None] = mapped_column(String(64))
    input_policy: Mapped[str] = mapped_column(String(50), default="pilot_retained_sources_v1")
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    __table_args__ = (UniqueConstraint("case_id", "version"),)


class EvidenceFragment(Base):
    __tablename__ = "evidence_fragments"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    version_id: Mapped[UUID] = mapped_column(ForeignKey("evidence_versions.id"), index=True)
    source: Mapped[str] = mapped_column(String(30))
    policy_version: Mapped[str] = mapped_column(String(50))
    observed_at: Mapped[datetime | None]
    retrieved_at: Mapped[datetime]
    expires_at: Mapped[datetime] = mapped_column(index=True)
    payload: Mapped[dict | None]
    content_sha256: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(40))
    __table_args__ = (
        CheckConstraint(
            "source IN ('GEMINI','NASA_FIRMS','SENTINEL_5P',"
            "'GOOGLE_AQ','GOOGLE_WEATHER','GOOGLE_FORECAST','RULES')",
            name="source",
        ),
        CheckConstraint(
            "(state='AVAILABLE' AND payload IS NOT NULL AND content_sha256 IS NOT NULL) "
            "OR (state<>'AVAILABLE' AND payload IS NULL AND content_sha256 IS NULL)",
            name="content_state",
        ),
        CheckConstraint(
            "state IN ('AVAILABLE','NOT_RETAINED_BY_POLICY','EXPIRED_BY_SOURCE_POLICY',"
            "'DELETED','UNAVAILABLE','NOT_APPLICABLE')",
            name="state",
        ),
        CheckConstraint(
            "source NOT IN ('GOOGLE_AQ','GOOGLE_WEATHER','GOOGLE_FORECAST') "
            "OR (payload IS NULL AND content_sha256 IS NULL AND state='NOT_RETAINED_BY_POLICY')",
            name="no_google_content",
        ),
    )


class EvidenceRedaction(Base):
    __tablename__ = "evidence_redactions"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    fragment_id: Mapped[UUID] = mapped_column(ForeignKey("evidence_fragments.id"), unique=True)
    reason: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime]


class ReviewEvent(Base):
    __tablename__ = "review_events"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id"), index=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    unit_id: Mapped[UUID | None] = mapped_column(ForeignKey("units.id"))
    revision: Mapped[int]
    action: Mapped[str] = mapped_column(String(50))
    evidence_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("evidence_versions.id"))
    created_at: Mapped[datetime]
    reason: Mapped[str | None] = mapped_column(String(2000))
    task_id: Mapped[UUID | None] = mapped_column(ForeignKey("verification_tasks.id"))
    __table_args__ = (UniqueConstraint("case_id", "revision"),)


class InternalNote(Base):
    __tablename__ = "internal_notes"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id"), index=True)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]


class ReporterUpdate(Base):
    __tablename__ = "reporter_updates"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id"), index=True)
    publisher_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30))
    message: Mapped[str | None] = mapped_column(String(1000))
    published_at: Mapped[datetime]
    case_revision: Mapped[int | None]
    expires_at: Mapped[datetime]
    __table_args__ = (
        CheckConstraint(
            "status IN ('RECEIVED','IN_REVIEW','FOLLOW_UP_PLANNED','UPDATE_AVAILABLE','CLOSED')",
            name="status",
        ),
    )


class VerificationTask(Base):
    __tablename__ = "verification_tasks"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id"), index=True)
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    assigned_to: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    state: Mapped[str] = mapped_column(String(20), default="REQUESTED")
    revision: Mapped[int] = mapped_column(default=0)
    instructions: Mapped[str | None] = mapped_column(String(2000))
    outcome: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    completed_at: Mapped[datetime | None]
    __table_args__ = (
        CheckConstraint("state IN ('REQUESTED','ASSIGNED','COMPLETED','CANCELLED')", name="state"),
    )


class Job(Base):
    """One durable logical run; lease tokens fence individual worker deliveries."""

    __tablename__ = "jobs"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(ForeignKey("reports.id"), index=True)
    request_id: Mapped[UUID] = mapped_column(unique=True)
    kind: Mapped[str] = mapped_column(String(30))
    state: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime]
    next_run_at: Mapped[datetime | None]
    lease_token: Mapped[UUID | None]
    lease_expires_at: Mapped[datetime | None]
    heartbeat_at: Mapped[datetime | None]
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    completed_at: Mapped[datetime | None]
    safe_reason: Mapped[str | None] = mapped_column(String(50))
    requested_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    authorized_unit_id: Mapped[UUID | None] = mapped_column(ForeignKey("units.id"))
    __table_args__ = (
        CheckConstraint(
            "kind IN ('PROCESS_REPORT','REFRESH_EVIDENCE','MANUAL_ENRICHMENT')", name="kind"
        ),
        CheckConstraint(
            "state IN ('PENDING','RUNNING','RETRY_WAIT','SUCCEEDED','PARTIAL',"
            "'FAILED','CANCELLED')",
            name="state",
        ),
        CheckConstraint("attempts BETWEEN 0 AND 3", name="attempts"),
        Index("ix_jobs_due", "state", "next_run_at", "lease_expires_at"),
    )


class ProcessingMetric(Base):
    """Bounded operational metadata only: no location, identity, URL or provider payload."""

    __tablename__ = "processing_metrics"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(20))
    outcome: Mapped[str] = mapped_column(String(30))
    duration_ms: Mapped[int]
    usage_units: Mapped[int]
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    __table_args__ = (CheckConstraint("duration_ms >= 0 AND usage_units >= 0", name="nonnegative"),)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    principal_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    operation: Mapped[str] = mapped_column(String(30))
    key: Mapped[UUID]
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    key_created_at: Mapped[datetime]
    report_id: Mapped[UUID] = mapped_column(ForeignKey("reports.id"))
    result_id: Mapped[UUID | None]
    consumed_until: Mapped[datetime]
    tombstone: Mapped[bool] = mapped_column(default=False)
    __table_args__ = (UniqueConstraint("principal_id", "operation", "key"),)


class PrivacyRequest(Base):
    __tablename__ = "privacy_requests"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(ForeignKey("reports.id"), unique=True)
    requested_at: Mapped[datetime]
    purge_due_at: Mapped[datetime]
    purged_at: Mapped[datetime | None]
    ledger_expires_at: Mapped[datetime]


class InformationRequest(Base):
    __tablename__ = "information_requests"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id"), index=True)
    update_id: Mapped[UUID] = mapped_column(ForeignKey("reporter_updates.id"), unique=True)
    prompt: Mapped[str | None] = mapped_column(String(1000))
    state: Mapped[str] = mapped_column(String(20), default="OPEN")
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    __table_args__ = (CheckConstraint("state IN ('OPEN','ANSWERED','CLOSED')", name="state"),)


class ReportSupplement(Base):
    __tablename__ = "report_supplements"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    report_id: Mapped[UUID] = mapped_column(ForeignKey("reports.id"), index=True)
    request_id: Mapped[UUID] = mapped_column(ForeignKey("information_requests.id"), unique=True)
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str | None] = mapped_column(String(2000))
    accepted_at: Mapped[datetime]
    case_revision: Mapped[int | None]
    expires_at: Mapped[datetime]


Index("ix_cases_unit_created", Case.assigned_unit_id, Case.created_at)


class MaintenanceHeartbeat(Base):
    __tablename__ = "maintenance_heartbeats"
    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    succeeded_at: Mapped[datetime]


class RecoveryControl(Base):
    """Out-of-band epoch must match before a runtime may serve this database."""

    __tablename__ = "recovery_control"
    name: Mapped[str] = mapped_column(String(20), primary_key=True)
    epoch: Mapped[UUID | None]
    state: Mapped[str] = mapped_column(String(20))
    manifest_sha256: Mapped[str | None] = mapped_column(String(64))
    lock_guard: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    applied_at: Mapped[datetime | None]
    released_at: Mapped[datetime | None]
    __table_args__ = (CheckConstraint("state IN ('QUARANTINED','READY')", name="state"),)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    name: Mapped[str] = mapped_column(String(20), primary_key=True)
    succeeded_at: Mapped[datetime]
