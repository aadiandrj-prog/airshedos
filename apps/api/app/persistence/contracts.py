"""Internal commands/projections, deliberately not mounted as unauthenticated APIs."""

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.citizen.models import VisualInterpretation
from app.environment.models import FireObservation, SatelliteAtmosphericContext


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class Principal:
    """Trusted internal seam, NOT authentication. Phase 2 must construct after verification.

    No default principal, HTTP dependency, body field or environment bypass exists.
    A matching active database identity is still required on each repository action.
    """

    issuer: str
    subject: str
    session_id: UUID | None = None
    unit_id: UUID | None = None  # Requested scope; membership still comes from SQL.


class ReportSubmission(StrictModel):
    description: str = Field(min_length=1, max_length=2000)
    declared_category: Literal["SMOKE_OR_BURNING", "DUST", "ODOUR", "OTHER", "UNSURE"]
    reported_latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    reported_longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    declared_capture_at: AwareDatetime | None = None
    media_id: UUID | None = None
    reported_place: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("description")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Description is required")
        return value


class Retention(StrictModel):
    # Configurable downwards; extending any ceiling requires a new policy review.
    report_days: int = Field(default=90, ge=1, le=90)
    media_days: int = Field(default=30, ge=1, le=30)
    staging_seconds: int = Field(default=3600, ge=1, le=3600)
    source_days: int = Field(default=30, ge=1, le=30)
    audit_days: int = Field(default=180, ge=180, le=180)


class Acceptance(StrictModel):
    report_id: UUID
    case_id: UUID
    receipt_id: UUID
    accepted_at: datetime
    status: Literal["RECEIVED"] = "RECEIVED"
    processing: Literal["PENDING"] = "PENDING"
    replayed: bool = False


class Location(StrictModel):
    latitude: float
    longitude: float


class MediaRead(StrictModel):
    id: UUID
    state: str
    expires_at: datetime


class PublishedUpdate(StrictModel):
    id: UUID
    status: str
    message: str | None
    published_at: datetime
    timeline_order: int | None = None


class ProcessingRead(StrictModel):
    state: str
    safe_reason: str | None
    visual_state: str = "PENDING"


class InformationRequestRead(StrictModel):
    id: UUID
    prompt: str | None
    state: str
    created_at: datetime
    expires_at: datetime


class SupplementRead(StrictModel):
    id: UUID
    request_id: UUID
    body: str | None
    accepted_at: datetime
    media: MediaRead | None
    timeline_order: int | None = None


class ResidentReportDetail(StrictModel):
    content_expires_at: datetime
    id: UUID
    receipt_id: UUID
    accepted_at: datetime
    description: str
    reported_place: str | None = None
    declared_category: str
    reported_location: Location
    declared_capture_at: datetime | None
    capture_time_basis: str
    media: MediaRead | None
    reporter_status: str
    published_updates: list[PublishedUpdate]
    processing: ProcessingRead
    withdrawn_at: datetime | None
    deletion_state: str
    information_requests: list[InformationRequestRead] = Field(default_factory=list)
    supplements: list[SupplementRead] = Field(default_factory=list)


class AuthorityCaseDetail(StrictModel):
    id: UUID
    report_id: UUID
    assigned_unit_id: UUID
    review_state: str
    revision: int
    latest_evidence_version_id: UUID | None
    description: str
    reported_location: Location
    declared_capture_at: datetime | None
    capture_time_basis: str
    # Separate projection: no reporter identity, object paths or token/session fields.
    internal_notes: list[str]
    history: list[dict]


class FirmsPayload(StrictModel):
    kind: Literal["firms_normalized_v1"] = "firms_normalized_v1"
    dataset: Literal["VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT", "VIIRS_SNPP_NRT"]
    detection_count: int = Field(ge=0, le=100000)
    nearest_distance_km: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class SentinelPayload(StrictModel):
    kind: Literal["sentinel_normalized_v1"] = "sentinel_normalized_v1"
    product: Literal["COPERNICUS/S5P/NRTI/L3_NO2", "COPERNICUS/S5P/NRTI/L3_SO2"]
    column_mol_m2: float = Field(allow_inf_nan=False)
    valid_pixel_count: int = Field(ge=1)


class GeminiPayload(StrictModel):
    kind: Literal["gemini_normalized_v1"] = "gemini_normalized_v1"
    interpretation: VisualInterpretation
    model: Literal["gemini-3.1-flash-lite"] = "gemini-3.1-flash-lite"
    prompt_version: Literal["citizen_evidence_v1"] = "citizen_evidence_v1"
    model_version: str | None = Field(default=None, max_length=200)


class RetainedFiresPayload(StrictModel):
    kind: Literal["firms_normalized_v2"] = "firms_normalized_v2"
    dataset: str = Field(max_length=50)
    observations: list[FireObservation] = Field(max_length=500)


class RetainedSatellitePayload(StrictModel):
    kind: Literal["sentinel_normalized_v2"] = "sentinel_normalized_v2"
    context: SatelliteAtmosphericContext


class RetainedRule(StrictModel):
    rule_id: str
    source: str
    verdict: str
    summary: str


class RetainedAssessmentPayload(StrictModel):
    kind: Literal["retained_assessment_v1"] = "retained_assessment_v1"
    support_level: Literal["STRONG", "MODERATE", "WEAK", "INSUFFICIENT", "CONFLICTING"]
    event_type: str | None
    recommended_next_step: str
    reason_code: Literal[
        "DETERMINISTIC_ADVISORY", "NO_VISUAL_HYPOTHESIS", "NO_VISUAL_INTERPRETATION"
    ]
    explanation: str
    temporal_basis: Literal["submission_time_proxy"] = "submission_time_proxy"
    rules: list[RetainedRule] = Field(max_length=20)


class FragmentInput(StrictModel):
    # Discriminated normalized fields; never arbitrary raw provider JSON/composite snapshots.
    payload: Annotated[
        FirmsPayload
        | SentinelPayload
        | GeminiPayload
        | RetainedFiresPayload
        | RetainedSatellitePayload
        | RetainedAssessmentPayload,
        Field(discriminator="kind"),
    ]
    retrieved_at: AwareDatetime
    observed_at: AwareDatetime | None = None


class PersistenceError(Exception):
    """Safe messages only; future HTTP adapter translates these without SQL/parameters."""


class RecoveryUnavailable(PersistenceError):
    pass


class NotFound(PersistenceError):
    pass


class AccessDenied(PersistenceError):
    pass


class Conflict(PersistenceError):
    pass


class Gone(PersistenceError):
    pass


class RateLimited(PersistenceError):
    pass
