import hashlib
import json

from app.corroboration.models import (
    CorroborationAssessment,
    EventFamily,
    NextStep,
    SourceSummary,
    StructuredReport,
    SupportLevel,
    Verdict,
)
from app.corroboration.rules import POSITIVE, RuleEvaluation
from app.corroboration.settings import CorroborationSettings
from app.environment.models import EnvironmentalContext
from app.models import Provenance


def aggregate(family, event_type, rules):
    visual, aq, fires, *_ = rules
    if any(r.verdict == Verdict.CONTRADICTS for r in rules):
        return (
            SupportLevel.CONFLICTING,
            NextStep.REVIEW,
            "Structured visual fields disagree; review before relying on this interpretation.",
        )
    if family == EventFamily.NONE_OR_UNCERTAIN or visual.verdict not in POSITIVE:
        step = (
            NextStep.NO_ACTION_FROM_CURRENT_EVIDENCE
            if event_type == "no_visible_pollution"
            else NextStep.REVIEW
        )
        return (
            SupportLevel.INSUFFICIENT,
            step,
            "No sufficiently clear visual event hypothesis to corroborate.",
        )
    if all(
        r.verdict in {Verdict.UNAVAILABLE, Verdict.STALE, Verdict.NOT_APPLICABLE} for r in rules[1:]
    ):
        return (
            SupportLevel.INSUFFICIENT,
            NextStep.REVIEW,
            "No fresh applicable environmental evidence is available for corroboration.",
        )
    if visual.verdict == Verdict.SUPPORTS and fires.verdict == Verdict.SUPPORTS:
        return (
            SupportLevel.STRONG,
            NextStep.FIELD_VERIFICATION,
            "High ordinal visual support and a very nearby recent nominal/high-confidence fire "
            "detection support field verification. This establishes neither truth nor causality.",
        )
    if aq.verdict in POSITIVE or fires.verdict in POSITIVE:
        return (
            SupportLevel.MODERATE,
            NextStep.FIELD_VERIFICATION,
            "Visual support joins indirect particulate context or nearby fire support. "
            "AQ cannot identify a source category; satellite and wind cannot raise this level.",
        )
    return (
        SupportLevel.WEAK,
        NextStep.MONITOR,
        "Visual support exists; environmental context adds no independent event support.",
    )


def assess(
    record: StructuredReport, context: EnvironmentalContext, settings: CorroborationSettings
) -> CorroborationAssessment:
    evaluation = RuleEvaluation(record, context, settings)
    rules = evaluation.evaluate()
    level, step, explanation = aggregate(evaluation.family, record.analysis.event_type, rules)
    statuses = [
        "live",
        context.source_statuses.air_quality.status,
        context.source_statuses.fires.status,
        context.source_statuses.weather.status,
    ]
    for product in ("no2", "co", "aerosol_index"):
        item = (
            next((p for p in context.satellite.products if p.product == product), None)
            if context.satellite
            else None
        )
        statuses.append(item.status if item else "unavailable")
    result = CorroborationAssessment(
        id="pending",
        report_id=record.report.id,
        generated_at=context.generated_at,
        event_type=record.analysis.event_type,
        event_family=evaluation.family,
        support_level=level,
        recommended_next_step=step,
        submission_time=record.report.created_at,
        rules=rules,
        aggregation_explanation=explanation,
        contributing_rule_ids=[r.rule_id for r in rules if r.verdict in POSITIVE],
        source_summary=[
            SourceSummary(source=r.source, status=status, verdict=r.verdict, message=r.summary)
            for r, status in zip(rules, statuses, strict=True)
        ],
        environmental_context=context,
        limitations=[
            "Image capture time is unknown; environmental context is aligned to report submission "
            "time rather than verified capture time.",
            "AQ/weather/FIRMS use current lookup; satellite uses a window ending at submission. "
            "Observation ages and signed offsets are explicit; the sources are not simultaneous.",
            "Corroboration does not establish event truth, source causality, legal responsibility, "
            "emission quantity, a regulatory violation or precise health impact.",
            "Support levels are deterministic checklist categories, not calibrated probabilities.",
            "Citizen text is unverified context and never independently contributes support.",
            "Satellite atmospheric columns are regional context and are not equivalent to "
            "ground-level pollutant concentrations. All three satellite products are context only.",
            "No detection, satisfactory AQ or missing coverage cannot rule out a local event.",
            "Wind is a single-location approximation; spatial variability and unknown image time "
            "prevent plume or source attribution. Recommendations are advisory only.",
        ],
        provenance=Provenance(
            source_id=record.report.id,
            method="deterministic_corroboration_v1",
            is_demo=False,
            note="Server-owned structured evidence and normalized "
            "environmental observations; no additional model call or incident mutation.",
        ),
    )
    # Same normalized evidence, policy and timestamps -> byte-for-byte identical result.
    digest = hashlib.sha256(
        json.dumps(
            {
                "assessment": result.model_dump(mode="json", exclude={"id"}),
                "settings": settings.model_dump(mode="json"),
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()[:24]
    result.id = f"CA-{digest}"
    return result
