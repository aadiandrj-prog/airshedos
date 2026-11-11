from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.persistence.contracts import (
    AuthorityCaseDetail,
    InformationRequestRead,
    MediaRead,
    PublishedUpdate,
    StrictModel,
    SupplementRead,
)


class EmptyCommand(StrictModel):
    pass


class RevisionCommand(StrictModel):
    expected_revision: int = Field(ge=0)


class ReasonCommand(RevisionCommand):
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("A reason or finding is required")
        return value


class AssignmentCommand(RevisionCommand):
    membership_id: UUID | None = None  # Selection only; target scope/role comes from SQL.
    claim_self: bool = False


class NoteCommand(RevisionCommand):
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Text is required")
        return value


class PublicationCommand(RevisionCommand):
    status: Literal["IN_REVIEW", "FOLLOW_UP_PLANNED", "UPDATE_AVAILABLE", "CLOSED"]
    message: str = Field(min_length=1, max_length=1000)

    @field_validator("message")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Public message is required")
        return value


class InformationCommand(RevisionCommand):
    prompt: str = Field(min_length=1, max_length=1000)


class ReferenceCommand(RevisionCommand):
    reference: str = Field(min_length=1, max_length=200, pattern=r"^[^\x00-\x1f\x7f]+$")


class FieldCommand(ReasonCommand):
    action: Literal["CLAIM", "ASSIGN", "COMPLETE", "CANCEL"]
    membership_id: UUID | None = None


class FieldRead(StrictModel):
    id: UUID
    state: str
    assigned_member_id: UUID | None
    instructions: str | None
    outcome: str | None
    created_at: datetime
    completed_at: datetime | None
    revision: int


class AttemptRead(StrictModel):
    request_id: UUID
    stage: str
    state: str
    safe_reason: str | None
    started_at: datetime | None
    ended_at: datetime | None
    request_created_at: datetime


class VersionRead(StrictModel):
    id: UUID
    version: int
    created_at: datetime
    expires_at: datetime
    input_policy: str


class AuthorityWorkspace(AuthorityCaseDetail):
    receipt_id: UUID
    accepted_at: datetime
    content_expires_at: datetime
    reported_place: str | None
    declared_category: str
    withdrawn_at: datetime | None
    assigned_member_id: UUID | None
    permitted_review_states: list[str]
    media: MediaRead | None
    processing_attempts: list[AttemptRead]
    evidence_versions: list[VersionRead]
    field_follow_ups: list[FieldRead]
    published_updates: list[PublishedUpdate]
    information_requests: list[InformationRequestRead]
    supplements: list[SupplementRead]
    external_reference: str | None


class RevisionRead(StrictModel):
    revision: int


class EnrichmentRead(StrictModel):
    request_id: UUID
    version_id: UUID | None
    state: str
    notice: str = (
        "Durably queued; processing is independent of human review. "
        "No review decision or resident update was made."
    )


class AuthorityPacket(StrictModel):
    schema_version: Literal["pilot_case_packet_v2"] = "pilot_case_packet_v2"
    delivery_mode: Literal["MANUAL_EXPORT"] = "MANUAL_EXPORT"
    visibility: Literal["UNIT_REVIEW_METADATA"] = "UNIT_REVIEW_METADATA"
    created_at: datetime
    packet: dict
    sha256: str
    notice: str = (
        "Manual copy; no government delivery or receipt. "
        "No identity, note bodies, exact location, media or provider payloads."
    )
