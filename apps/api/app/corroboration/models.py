from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, JsonValue, model_validator

from app.citizen.models import (
    CitizenVisualSignal,
    EventType,
    GeminiEvidenceAnalysis,
    ModelProvenance,
)
from app.environment.models import EnvironmentalContext, EnvironmentalProvenance, SourceState
from app.models import CitizenReport, DomainModel, Provenance


class EventFamily(StrEnum):
    COMBUSTION = "COMBUSTION"
    DUST = "DUST"
    ATMOSPHERIC_HAZE = "ATMOSPHERIC_HAZE"
    TRAFFIC = "TRAFFIC"
    NONE_OR_UNCERTAIN = "NONE_OR_UNCERTAIN"


class Verdict(StrEnum):
    SUPPORTS = "SUPPORTS"
    WEAKLY_SUPPORTS = "WEAKLY_SUPPORTS"
    NEUTRAL = "NEUTRAL"
    CONTRADICTS = "CONTRADICTS"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SupportLevel(StrEnum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    INSUFFICIENT = "INSUFFICIENT"
    CONFLICTING = "CONFLICTING"


class NextStep(StrEnum):
    FIELD_VERIFICATION = "FIELD_VERIFICATION"
    MONITOR = "MONITOR"
    REVIEW = "REVIEW"
    NO_ACTION_FROM_CURRENT_EVIDENCE = "NO_ACTION_FROM_CURRENT_EVIDENCE"


class StructuredReport(DomainModel):
    report: CitizenReport
    analysis: GeminiEvidenceAnalysis
    evidence: CitizenVisualSignal

    @model_validator(mode="after")
    def matching_report(self):
        if self.report.image_url is not None:
            raise ValueError("Ephemeral reports cannot contain image references")
        if any(
            ref != self.report.id
            for ref in (
                self.analysis.source_report_id,
                self.evidence.source_report_id,
                self.analysis.provenance.source_report_id,
                self.evidence.provenance.source_report_id,
            )
        ):
            raise ValueError("Structured evidence must refer to the same report")
        return self


class EvidenceReference(DomainModel):
    source_id: str
    observed_at: AwareDatetime | None
    retrieved_at: AwareDatetime
    age_seconds: float | None
    submission_offset_seconds: float | None
    provenance: ModelProvenance | EnvironmentalProvenance | Provenance


class CorroborationRuleResult(DomainModel):
    rule_id: str
    source: str
    verdict: Verdict
    summary: str
    inputs_used: dict[str, JsonValue]
    evidence_references: list[EvidenceReference]
    generated_at: AwareDatetime


class SourceSummary(DomainModel):
    source: str
    status: SourceState
    verdict: Verdict
    message: str


class CorroborationAssessment(DomainModel):
    id: str
    report_id: str
    generated_at: AwareDatetime
    event_type: EventType
    event_family: EventFamily
    support_level: SupportLevel
    recommended_next_step: NextStep
    temporal_basis: Literal["submission_time_proxy"] = "submission_time_proxy"
    submission_time: AwareDatetime
    rules: list[CorroborationRuleResult]
    aggregation_explanation: str
    contributing_rule_ids: list[str]
    source_summary: list[SourceSummary]
    environmental_context: EnvironmentalContext
    limitations: list[str]
    provenance: Provenance
    policy_version: Literal["corroboration_v1"] = "corroboration_v1"


class ReportUnavailable(DomainModel):
    detail: str = "Report expired or unavailable. Analyze the image again to corroborate it."
