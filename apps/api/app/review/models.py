from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field

from app.corroboration.models import CorroborationAssessment, StructuredReport, SupportLevel
from app.models import DomainModel, Latitude, Longitude


class ReviewState(StrEnum):
    NEW = "NEW"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    MONITORING = "MONITORING"
    CLOSED_NO_ACTION = "CLOSED_NO_ACTION"


TRANSITIONS = {
    ReviewState.NEW: [ReviewState.UNDER_REVIEW],
    ReviewState.UNDER_REVIEW: [
        ReviewState.ACKNOWLEDGED,
        ReviewState.MONITORING,
        ReviewState.CLOSED_NO_ACTION,
    ],
    ReviewState.ACKNOWLEDGED: [ReviewState.MONITORING, ReviewState.CLOSED_NO_ACTION],
    ReviewState.MONITORING: [
        ReviewState.UNDER_REVIEW,
        ReviewState.ACKNOWLEDGED,
        ReviewState.CLOSED_NO_ACTION,
    ],
    ReviewState.CLOSED_NO_ACTION: [],
}
ORDER = {
    state: rank
    for rank, states in enumerate(
        [
            [ReviewState.NEW],
            [ReviewState.UNDER_REVIEW],
            [ReviewState.ACKNOWLEDGED, ReviewState.MONITORING],
            [ReviewState.CLOSED_NO_ACTION],
        ]
    )
    for state in states
}


class JurisdictionResolution(DomainModel):
    state: Literal["Delhi", "Haryana", "Uttar Pradesh", "Unknown"]
    area: str | None = None
    method: Literal["prototype_lookup_area_v1"] = "prototype_lookup_area_v1"
    authoritative: Literal[False] = False
    note: str = (
        "Configuration-backed prototype area, not an official administrative boundary. "
        "Informational only; verify jurisdiction independently. No authority routing."
    )


class OfficerReview(DomainModel):
    state: ReviewState = ReviewState.NEW
    revision: Annotated[int, Field(ge=0)] = 0
    action_at: AwareDatetime | None = None
    allowed_transitions: list[ReviewState] = Field(
        default_factory=lambda: [ReviewState.UNDER_REVIEW]
    )


class ReviewRequest(DomainModel):
    state: ReviewState
    expected_revision: Annotated[int, Field(ge=0)]


class CaseSnapshot(DomainModel):
    record: StructuredReport
    assessment: CorroborationAssessment
    jurisdiction: JurisdictionResolution
    evidence_sha256: str


class OfficerCase(DomainModel):
    id: str
    created_at: AwareDatetime
    expires_at: AwareDatetime
    snapshot: CaseSnapshot
    review: OfficerReview
    storage: Literal["ephemeral_process_local"] = "ephemeral_process_local"


class CaseSummary(DomainModel):
    id: str
    report_id: str
    event_type: str
    latitude: Latitude
    longitude: Longitude
    submitted_at: AwareDatetime
    expires_at: AwareDatetime
    is_synthetic: bool
    jurisdiction: JurisdictionResolution
    support_level: SupportLevel
    review: OfficerReview
