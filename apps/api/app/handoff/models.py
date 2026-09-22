from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StrictInt, model_validator

from app.citizen.models import EventType, GeminiEvidenceAnalysis
from app.corroboration.models import EventFamily, EvidenceReference, NextStep, SupportLevel, Verdict
from app.environment.forecast_models import ForecastSummary, HourlyAirQualityForecast
from app.environment.models import (
    AirQualityObservation,
    EnvironmentalProvenance,
    FireObservation,
    MeteorologicalObservation,
    SatelliteAvailability,
    SatelliteObservation,
    SatelliteProduct,
    SourceState,
)
from app.models import DomainModel, Latitude, Longitude, Provenance
from app.review.models import JurisdictionResolution, ReviewState

PositiveVersion = Annotated[StrictInt, Field(ge=1)]
Revision = Annotated[StrictInt, Field(ge=0)]


class HandoffJurisdiction(StrEnum):
    DELHI = "DELHI"
    HARYANA = "HARYANA"
    UTTAR_PRADESH = "UTTAR_PRADESH"


class HandoffReason(StrEnum):
    CROSS_BORDER_EVENT = "CROSS_BORDER_EVENT"
    DOWNWIND_IMPACT = "DOWNWIND_IMPACT"
    JURISDICTION_MISMATCH = "JURISDICTION_MISMATCH"
    SHARED_CORRIDOR_CONTEXT = "SHARED_CORRIDOR_CONTEXT"
    MANUAL_OFFICER_HANDOFF = "MANUAL_OFFICER_HANDOFF"


class HandoffState(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    SENT_SIMULATED = "SENT_SIMULATED"
    RECEIVED = "RECEIVED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    RETURNED_FOR_REVIEW = "RETURNED_FOR_REVIEW"


TRANSITIONS = {
    HandoffState.DRAFT: [HandoffState.READY],
    HandoffState.READY: [HandoffState.SENT_SIMULATED],
    HandoffState.SENT_SIMULATED: [HandoffState.RECEIVED],
    HandoffState.RECEIVED: [
        HandoffState.ACCEPTED,
        HandoffState.REJECTED,
        HandoffState.RETURNED_FOR_REVIEW,
    ],
    HandoffState.RETURNED_FOR_REVIEW: [HandoffState.READY],
    HandoffState.ACCEPTED: [],
    HandoffState.REJECTED: [],
}


class EventLocation(DomainModel):
    latitude: Latitude
    longitude: Longitude
    location_precision: Literal["reported_coordinate_accuracy_unknown"]
    jurisdiction_at_location: JurisdictionResolution


class EventTemporal(DomainModel):
    report_submitted_at: AwareDatetime
    image_capture_time_known: Literal[False]
    image_capture_time: None
    environmental_reference_time: AwareDatetime
    environmental_context_generated_at: AwareDatetime
    temporal_basis: Literal["submission_time_proxy"]


class EventSourceStatus(DomainModel):
    provider: str
    status: SourceState
    retrieved_at: AwareDatetime | None


class EventRule(DomainModel):
    rule_id: str
    source: str
    verdict: Verdict
    summary: str
    generated_at: AwareDatetime
    evidence_references: list[EvidenceReference]


class SatelliteEvidence(DomainModel):
    product: SatelliteProduct
    status: SourceState
    availability: SatelliteAvailability
    collection: str
    band: str
    unit: str
    observation: SatelliteObservation | None


class EventEvidence(DomainModel):
    report_id: str
    is_synthetic: bool
    citizen_evidence_summary: Literal[
        "Structured visual interpretation; raw image and citizen text omitted."
    ]
    gemini: GeminiEvidenceAnalysis
    source_statuses: list[EventSourceStatus]
    rules: list[EventRule]
    air_quality: AirQualityObservation | None
    weather: MeteorologicalObservation | None
    fires: list[FireObservation] | None
    fire_search_radius_km: float
    satellite: list[SatelliteEvidence] | None
    assessment_provenance: Provenance
    source_snapshot_sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class EventForecast(DomainModel):
    provider: Literal["google_air_quality_forecast"]
    status: SourceState
    retrieved_at: AwareDatetime | None
    issued_at: None
    summaries: list[ForecastSummary]
    hourly_forecasts: list[HourlyAirQualityForecast]
    provenance: EnvironmentalProvenance
    independence_note: str


class PollutionEvent(DomainModel):
    # No default: omission must be rejected, not silently treated as the current schema.
    schema_version: Literal["pollution_event_v1"]
    event_id: str
    case_id: str
    event_version: PositiveVersion
    created_at: AwareDatetime
    updated_at: AwareDatetime
    origin_jurisdiction: HandoffJurisdiction
    origin_system: Literal["AirshedOS prototype"]
    origin_case_id: str
    destination_jurisdiction: HandoffJurisdiction
    handoff_reason: HandoffReason
    origin_basis: Literal["manual_prototype_control_room"]
    location: EventLocation
    possible_event_type: EventType
    event_family: EventFamily
    corroboration_support: SupportLevel
    advisory_next_step: NextStep
    review_state: ReviewState
    source_review_revision: Revision
    temporal: EventTemporal
    evidence: EventEvidence
    forecast: EventForecast | None
    limitations: list[str]
    handoff_id: str
    handoff_created_at: AwareDatetime
    simulated: Literal[True]

    @model_validator(mode="after")
    def coherent(self):
        if self.origin_jurisdiction == self.destination_jurisdiction:
            raise ValueError("Source and destination must differ")
        if self.origin_case_id != self.case_id:
            raise ValueError("Origin case mismatch")
        if self.evidence.report_id != self.evidence.gemini.source_report_id:
            raise ValueError("Evidence report mismatch")
        if self.updated_at != self.created_at or self.handoff_created_at != self.created_at:
            raise ValueError("Frozen packet creation times must match")
        if self.review_state not in (
            ReviewState.UNDER_REVIEW,
            ReviewState.ACKNOWLEDGED,
            ReviewState.MONITORING,
        ):
            raise ValueError("Case must be under active review before handoff")
        return self


class CreateHandoff(DomainModel):
    origin_jurisdiction: HandoffJurisdiction
    destination_jurisdiction: HandoffJurisdiction
    reason: HandoffReason
    expected_case_revision: Revision

    @model_validator(mode="after")
    def distinct(self):
        if self.origin_jurisdiction == self.destination_jurisdiction:
            raise ValueError("Choose a different destination jurisdiction")
        return self


class TransitionHandoff(DomainModel):
    state: HandoffState
    expected_revision: Revision


class HandoffAudit(DomainModel):
    sequence: Revision
    timestamp: AwareDatetime
    action: Literal["CREATED"] | HandoffState
    state: HandoffState
    handoff_revision: Revision
    event_version: PositiveVersion
    origin_jurisdiction: HandoffJurisdiction
    destination_jurisdiction: HandoffJurisdiction
    payload_hash: str
    actor: Literal["source_control_room", "destination_control_room"]


class HandoffSummary(DomainModel):
    id: str
    case_id: str
    event_id: str
    event_version: PositiveVersion
    origin_jurisdiction: HandoffJurisdiction
    destination_jurisdiction: HandoffJurisdiction
    reason: HandoffReason
    possible_event_type: EventType
    corroboration_support: SupportLevel
    is_synthetic: bool
    created_at: AwareDatetime
    sent_at: AwareDatetime | None
    expires_at: AwareDatetime
    state: HandoffState
    revision: Revision
    payload_hash: str
    integrity: Literal["VERIFIED", "MISMATCH"]
    allowed_transitions: list[HandoffState]
    simulated: Literal[True] = True


class HandoffRecord(HandoffSummary):
    payload: PollutionEvent
    audit: list[HandoffAudit]
    audit_notice: Literal[
        "Ephemeral prototype audit trail; no authenticated identities or external delivery."
    ] = "Ephemeral prototype audit trail; no authenticated identities or external delivery."
