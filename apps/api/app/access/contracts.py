from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.persistence.contracts import StrictModel


class UnitRead(StrictModel):
    id: UUID
    name: str
    role: Literal["REVIEWER", "UNIT_ADMIN"]


class MeRead(StrictModel):
    id: UUID
    units: list[UnitRead]


class ResidentSummary(StrictModel):
    content_expires_at: datetime
    id: UUID
    receipt_id: UUID
    accepted_at: datetime
    processing: Literal["PENDING", "RUNNING", "SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"] = (
        "PENDING"
    )


class ResidentList(StrictModel):
    total: int
    items: list[ResidentSummary]


class AuthoritySummary(StrictModel):
    content_expires_at: datetime
    id: UUID
    created_at: datetime
    review_state: str
    revision: int
    reported_place: str | None = None
    declared_category: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    assigned_member_id: UUID | None = None


class AuthorityList(StrictModel):
    total: int
    items: list[AuthoritySummary]
    state_counts: dict[str, int]


class ReviewCommand(StrictModel):
    expected_revision: int = Field(ge=0)
    state: Literal["UNDER_REVIEW", "ACKNOWLEDGED", "MONITORING", "CLOSED_NO_ACTION", "REOPEN"]
    reason: str | None = Field(default=None, min_length=1, max_length=2000)


class ProposalCommand(StrictModel):
    target_subject: str = Field(min_length=1, max_length=255, pattern=r"^[^\s]+$")
    role: Literal["REVIEWER"] = "REVIEWER"


class ProposalRead(StrictModel):
    id: UUID
    state: Literal["PENDING", "APPROVED", "REJECTED"]


class MemberRead(StrictModel):
    id: UUID
    role: str
    state: str


class PilotCasePacket(StrictModel):
    schema_version: Literal["pilot_case_packet_v1"] = "pilot_case_packet_v1"
    delivery_mode: Literal["MANUAL_EXPORT"] = "MANUAL_EXPORT"
    case_id: UUID
    created_at: datetime
    review_state: str
    revision: int
    evidence_versions: list[dict]
    notice: Literal["Metadata only. No government delivery or receipt."] = (
        "Metadata only. No government delivery or receipt."
    )
