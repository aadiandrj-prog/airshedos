"""API domain contract. Probabilities use [0, 1]; all timestamps require timezones."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Probability = Annotated[float, Field(ge=0, le=1)]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]


class DomainModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", validate_assignment=True, json_schema_serialization_defaults_required=True
    )


class IncidentStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"


class RiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class SignalType(StrEnum):
    CITIZEN_REPORT = "citizen_report"
    AIR_QUALITY = "air_quality"
    FIRE = "fire"
    WIND = "wind"
    SATELLITE = "satellite"


class EvidenceStatus(StrEnum):
    INTERPRETED = "interpreted"
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    CONFLICTING = "conflicting"


class Jurisdiction(DomainModel):
    id: str
    name: str
    state: str
    authority_type: str


class CitizenReport(DomainModel):
    id: str
    created_at: AwareDatetime
    latitude: Latitude
    longitude: Longitude
    description: str
    language: str
    image_url: str | None = None
    source_type: Literal["citizen_report"] = "citizen_report"


class Provenance(DomainModel):
    source_id: str
    method: str
    is_demo: bool
    note: str


class EvidenceSignal(DomainModel):
    id: str
    signal_type: SignalType
    source: str
    status: EvidenceStatus
    confidence: Probability | None = None
    observed_at: AwareDatetime | None = None
    summary: str
    provenance: Provenance
    raw_reference: str | None = None

    @model_validator(mode="after")
    def validate_availability(self):
        if self.status == EvidenceStatus.INTERPRETED and self.confidence is not None:
            raise ValueError("Interpreted visual evidence has no incident confidence")
        if self.status == EvidenceStatus.UNAVAILABLE and self.confidence is not None:
            raise ValueError("Unavailable evidence cannot carry a confidence score")
        if (
            self.status not in (EvidenceStatus.UNAVAILABLE, EvidenceStatus.INTERPRETED)
            and self.observed_at is None
        ):
            raise ValueError("Available evidence requires an observation timestamp")
        return self


class ForecastRisk(DomainModel):
    horizon_hours: int = Field(gt=0, le=168)
    risk_level: RiskLevel
    spike_probability: Probability
    predicted_direction: str | None = None
    summary: str
    generated_at: AwareDatetime
    provenance: Provenance


class IncidentAction(DomainModel):
    id: str
    type: Literal["acknowledge", "share"]
    status: Literal["completed", "simulated"]
    created_at: AwareDatetime
    target_jurisdiction: Jurisdiction | None = None
    description: str


class PollutionIncident(DomainModel):
    id: str
    title: str
    event_type: Literal["probable_open_burning"]
    status: IncidentStatus
    severity: RiskLevel
    confidence: Probability
    latitude: Latitude
    longitude: Longitude
    detected_at: AwareDatetime
    updated_at: AwareDatetime
    jurisdiction: Jurisdiction
    evidence: list[EvidenceSignal]
    citizen_reports: list[CitizenReport]
    forecast: ForecastRisk
    recommended_action: str
    affected_jurisdictions: list[Jurisdiction]
    actions: list[IncidentAction] = Field(default_factory=list)
    model_version: str | None = None
    is_demo: bool
    field_verification_required: bool = True
    provenance: Provenance

    @model_validator(mode="after")
    def validate_timeline(self):
        if self.updated_at < self.detected_at:
            raise ValueError("updated_at cannot precede detected_at")
        return self


class ShareRequest(DomainModel):
    target_jurisdiction_id: str = Field(min_length=1, max_length=100)


class ShareResponse(DomainModel):
    simulated: Literal[True] = True
    action: IncidentAction
    incident: PollutionIncident
