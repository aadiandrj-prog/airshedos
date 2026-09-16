"""Visual interpretation only: no ground measurements, corroboration or causality."""

from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.models import CitizenReport, DomainModel, EvidenceSignal, Provenance

DISCLAIMER = (
    "AI interpretation — requires environmental corroboration. Visual evidence only; "
    "an image cannot establish pollutant concentration, source causality or a violation."
)
PROMPT_VERSION = "citizen_evidence_v1"


class EventType(StrEnum):
    OPEN_BURNING = "open_burning"
    INDUSTRIAL_SMOKE = "industrial_smoke"
    CONSTRUCTION_DUST = "construction_dust"
    ROAD_DUST = "road_dust"
    VEHICULAR_EMISSIONS = "vehicular_emissions"
    FIRE_OR_COMBUSTION = "fire_or_combustion"
    HAZE_OR_SMOG = "haze_or_smog"
    NO_VISIBLE_POLLUTION = "no_visible_pollution"
    UNCERTAIN = "uncertain"
    OTHER = "other"


class VisualConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VisualObservation(StrEnum):
    GRAY_PLUME = "Gray plume or cloud-like feature visible."
    DARK_PLUME = "Dark plume-like feature visible."
    FLAMES = "Flame-like features visible."
    TAN_CLOUD = "Tan dust-like cloud visible."
    REDUCED_VISIBILITY = "Reduced visibility or diffuse haze visible."
    CLOUD_FOG = "Cloud or fog-like features visible."
    OPEN_GROUND = "Open ground visible."
    BUILDINGS = "Buildings or structures visible."
    INDUSTRIAL_STRUCTURES = "Industrial-looking structures visible."
    CONSTRUCTION = "Construction equipment or exposed earth visible."
    TRAFFIC = "Vehicles or roadway visible."
    VEGETATION = "Vegetation visible."
    MATERIAL_PILE = "Pile of material visible; composition unknown."
    NO_FEATURES = "No clear smoke, flame or dust-like feature visible."
    INDOOR = "Indoor objects visible."
    LOW_LIGHT = "Low light limits visible detail."
    BLUR = "Blur or low resolution limits visible detail."


class VisualUncertainty(StrEnum):
    SOURCE_UNKNOWN = "Image alone cannot establish source or pollutant type."
    MATERIAL_UNKNOWN = "Material composition cannot be established visually."
    HAZE_AMBIGUITY = "Smoke, dust, cloud and fog can look similar."
    DISTANT = "Distant or obscured features limit interpretation."
    IMAGE_QUALITY = "Lighting, blur or resolution limits interpretation."
    TEXT_UNVERIFIED = "Citizen description is unverified context, not visual evidence."
    NO_MEASUREMENT = "Image alone cannot establish pollutant concentration or air quality."
    NO_EVENT = "No clear pollution-related event can be inferred from this image."
    SYNTHETIC = (
        "The image appears illustrative or synthetic; real conditions cannot be established."
    )


class VisualInterpretation(DomainModel):
    """Controlled model output; no free-text claims or identities can pass this boundary."""

    event_type: EventType
    event_type_confidence: VisualConfidence
    visible_smoke: bool | None
    visible_flames: bool | None
    visible_dust: bool | None
    industrial_context: bool | None
    construction_context: bool | None
    waste_burning_context: bool | None
    vegetation_burning_context: bool | None
    traffic_context: bool | None
    scene_type: Literal["outdoor", "indoor", "unclear"]
    apparent_scale: Literal["localized", "widespread_in_frame", "unclear"]
    visual_observations: list[VisualObservation] = Field(min_length=1, max_length=8)
    uncertainty_reasons: list[VisualUncertainty] = Field(min_length=1, max_length=8)
    insufficient_evidence: bool = Field(
        description="True only when visual ambiguity prevents choosing an event category. "
        "False for a clear no_visible_pollution scene. True requires uncertain with low confidence."
    )

    @model_validator(mode="after")
    def check_uncertainty(self):
        if self.insufficient_evidence and self.event_type != EventType.UNCERTAIN:
            raise ValueError("Insufficient evidence requires uncertain interpretation")
        if self.event_type == EventType.UNCERTAIN and self.event_type_confidence != "low":
            raise ValueError("Uncertain interpretation requires low confidence")
        return self


class ModelProvenance(Provenance):
    model: str
    model_version: str | None
    prompt_version: Literal["citizen_evidence_v1"] = PROMPT_VERSION
    generated_at: AwareDatetime
    source_report_id: str
    derived: Literal[True] = True
    author: Literal["model"] = "model"
    confidence_basis: Literal["model_estimated_ordinal_not_calibrated"] = (
        "model_estimated_ordinal_not_calibrated"
    )


class GeminiEvidenceAnalysis(VisualInterpretation):
    source_report_id: str
    analyzed_at: AwareDatetime
    provenance: ModelProvenance
    safety_note: Literal[
        "AI interpretation — requires environmental corroboration. Visual evidence only; "
        "an image cannot establish pollutant concentration, source causality or a violation."
    ] = DISCLAIMER


class CitizenVisualSignal(EvidenceSignal):
    source_report_id: str
    derived: Literal[True] = True
    provenance: ModelProvenance
    confidence: None = None
    observed_at: None = None
    interpretation_at: AwareDatetime
    # Upload time is not photo acquisition time; unknown EXIF timestamps are not invented.


class AnalysisStatus(StrEnum):
    INTERPRETED = "interpreted"
    NOT_CONFIGURED = "not_configured"
    AUTH_ERROR = "auth_error"
    MODEL_UNAVAILABLE = "model_unavailable"
    QUOTA_LIMITED = "quota_limited"
    TIMEOUT = "timeout"
    SAFETY_BLOCKED = "safety_blocked"
    INVALID_RESPONSE = "invalid_response"
    ERROR = "error"


class CitizenAnalysisResponse(DomainModel):
    request_id: str
    status: AnalysisStatus
    report: CitizenReport
    analysis: GeminiEvidenceAnalysis | None = None
    evidence: CitizenVisualSignal | None = None
    message: str
    latency_ms: float = Field(ge=0)


class CitizenInputError(DomainModel):
    status: Literal["invalid_input"] = "invalid_input"
    message: str
