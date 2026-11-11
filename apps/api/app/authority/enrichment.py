"""Shared advisory pipeline; durable scheduling and ownership live in processing/."""

import asyncio

from app.citizen.models import VisualInterpretation
from app.citizen.service import interpret
from app.corroboration.engine import assess
from app.corroboration.models import StructuredReport
from app.persistence.contracts import (
    FragmentInput,
    GeminiPayload,
    Gone,
    PersistenceError,
    RetainedAssessmentPayload,
    RetainedFiresPayload,
    RetainedRule,
    RetainedSatellitePayload,
)


class EvidenceCollector:
    def __init__(self, access, environment, analyzer, settings):
        self.access, self.repo, self.environment, self.analyzer, self.settings = (
            access,
            access.repo,
            environment,
            analyzer,
            settings,
        )

    def _check(self, principal, case_id):
        with self.repo.sessions.begin() as session:
            _, _, report = self.repo._case(session, principal, case_id)
            if report.withdrawn_at:
                raise Gone("Report withdrawn")

    async def collect(self, principal, case_id, snapshot, *, source_call=None):
        fragments = []
        states = {
            "VISUAL": ("NOT_APPLICABLE", "NO_IMAGE")
            if snapshot["media_id"] is None
            else ("FAILED", "NOT_RETAINED_BY_POLICY"),
            "ENVIRONMENT": ("FAILED", "NOT_RETAINED_BY_POLICY"),
            "CORROBORATION": ("FAILED", "NO_VISUAL_INTERPRETATION"),
            "FORECAST": ("NOT_APPLICABLE", "NOT_RETAINED_BY_POLICY"),
        }
        context = None
        visual = None
        if snapshot["approved"]:

            async def environment():
                self._check(principal, case_id)
                return await self.environment.retained_context(
                    snapshot["latitude"],
                    snapshot["longitude"],
                    snapshot["accepted_at"],
                    **({"source_call": source_call} if source_call else {}),
                )

            async def image():
                if snapshot["media_id"] is None:
                    return None
                self._check(principal, case_id)
                if self.access.media is None:
                    states["VISUAL"] = ("FAILED", "PRIVATE_STORAGE_UNAVAILABLE")
                    return None
                if self.analyzer.settings.model != "gemini-3.1-flash-lite":
                    raise ValueError("Model storage policy not approved")
                data = self.access.media.read(principal, snapshot["media_id"], case_id=case_id)

                async def invoke():
                    return await interpret(
                        self.analyzer,
                        data,
                        "image/jpeg",
                        snapshot["latitude"],
                        snapshot["longitude"],
                        snapshot["description"],
                    )

                result = (
                    await source_call("GEMINI", invoke, int(bool(self.analyzer.settings.project)))
                    if source_call
                    else await invoke()
                )
                # Align the existing deterministic adapter to the durable report/submission time.
                if result.analysis and result.evidence:
                    result.report.id = str(snapshot["report_id"])
                    result.report.created_at = snapshot["accepted_at"]
                    for obj in (result.analysis, result.evidence):
                        obj.source_report_id = str(snapshot["report_id"])
                        obj.provenance.source_report_id = str(snapshot["report_id"])
                        obj.provenance.source_id = str(snapshot["report_id"])
                return result

            context, visual = await asyncio.gather(environment(), image(), return_exceptions=True)
            for result in (context, visual):
                if isinstance(result, PersistenceError):
                    raise result
            if isinstance(context, BaseException):
                context = None
            if isinstance(visual, BaseException):
                visual = None
                states["VISUAL"] = ("FAILED", "PROVIDER_OR_SCHEMA_FAILURE")
            states["ENVIRONMENT"] = ("FAILED", "PROVIDERS_UNAVAILABLE")
            if context and context.fires is not None:
                fragments.append(
                    FragmentInput(
                        payload=RetainedFiresPayload(
                            dataset=context.fire_dataset, observations=context.fires
                        ),
                        retrieved_at=context.source_statuses.fires.retrieved_at
                        or context.generated_at,
                        observed_at=max((f.observed_at for f in context.fires), default=None),
                    )
                )
            if (
                context
                and context.satellite
                and any(p.observation for p in context.satellite.products)
            ):
                fragments.append(
                    FragmentInput(
                        payload=RetainedSatellitePayload(context=context.satellite),
                        retrieved_at=context.satellite.generated_at,
                        observed_at=max(
                            p.observation.observed_at
                            for p in context.satellite.products
                            if p.observation
                        ),
                    )
                )
            if fragments:
                states["ENVIRONMENT"] = (
                    "SUCCEEDED" if len(fragments) == 2 else "PARTIAL",
                    "RETAINED_SOURCES_ONLY",
                )
            if visual is not None:
                states["VISUAL"] = (
                    ("SUCCEEDED", None)
                    if visual.analysis
                    else ("FAILED", str(visual.status).upper())
                )
                if visual.analysis:
                    interpretation = VisualInterpretation.model_validate(
                        {k: getattr(visual.analysis, k) for k in VisualInterpretation.model_fields}
                    )
                    fragments.append(
                        FragmentInput(
                            payload=GeminiPayload(
                                interpretation=interpretation,
                                model_version=visual.analysis.provenance.model_version,
                            ),
                            retrieved_at=visual.analysis.analyzed_at,
                        )
                    )
        if snapshot["media_id"] is None:
            rule = RetainedAssessmentPayload(
                support_level="INSUFFICIENT",
                event_type=None,
                recommended_next_step="REVIEW",
                reason_code="NO_VISUAL_HYPOTHESIS",
                explanation=(
                    "Text-only report: no visual hypothesis exists. Independently available "
                    "context cannot establish a local source or clear the report."
                ),
                rules=[],
            )
        elif visual and visual.analysis and visual.evidence and context:
            # AQ/weather/forecast are absent. No Google values or derived copy are stored.
            result = assess(
                StructuredReport(
                    report=visual.report, analysis=visual.analysis, evidence=visual.evidence
                ),
                context,
                self.settings,
            )
            rule = RetainedAssessmentPayload(
                support_level=result.support_level,
                event_type=result.event_type,
                recommended_next_step=result.recommended_next_step,
                reason_code="DETERMINISTIC_ADVISORY",
                explanation=result.aggregation_explanation,
                rules=[
                    RetainedRule(
                        rule_id=r.rule_id, source=r.source, verdict=r.verdict, summary=r.summary
                    )
                    for r in result.rules
                ],
            )
        else:
            rule = None
        if rule:
            fragments.append(FragmentInput(payload=rule, retrieved_at=self.repo.clock()))
            states["CORROBORATION"] = ("SUCCEEDED", rule.reason_code)
        return fragments, states
