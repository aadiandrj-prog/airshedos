"""Allowlisted normalized evidence only; no raw media, citizen text or provider dumps."""

import hashlib
import json

from app.handoff.models import (
    CreateHandoff,
    EventEvidence,
    EventForecast,
    EventLocation,
    EventRule,
    EventSourceStatus,
    EventTemporal,
    PollutionEvent,
    SatelliteEvidence,
)
from app.review.models import OfficerCase


def canonical_bytes(event: PollutionEvent) -> bytes:
    # Named v1 encoding, not a claim of RFC 8785/JCS compliance. No trailing newline.
    return json.dumps(
        event.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def payload_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_packet(case: OfficerCase, request: CreateHandoff, version: int, handoff_id: str, now):
    record, assessment = case.snapshot.record, case.snapshot.assessment
    context = assessment.environmental_context
    forecast = assessment.forecast_outlook
    statuses = list(context.source_statuses.model_dump().values())
    if context.satellite:
        statuses.append(context.satellite.provider_status.model_dump())
    return PollutionEvent(
        schema_version="pollution_event_v1",
        event_id="PE-" + case.id,
        case_id=case.id,
        event_version=version,
        created_at=now,
        updated_at=now,
        origin_jurisdiction=request.origin_jurisdiction,
        origin_system="AirshedOS prototype",
        origin_case_id=case.id,
        destination_jurisdiction=request.destination_jurisdiction,
        handoff_reason=request.reason,
        origin_basis="manual_prototype_control_room",
        location=EventLocation(
            latitude=record.report.latitude,
            longitude=record.report.longitude,
            location_precision="reported_coordinate_accuracy_unknown",
            jurisdiction_at_location=case.snapshot.jurisdiction,
        ),
        possible_event_type=assessment.event_type,
        event_family=assessment.event_family,
        corroboration_support=assessment.support_level,
        advisory_next_step=assessment.recommended_next_step,
        review_state=case.review.state,
        source_review_revision=case.review.revision,
        temporal=EventTemporal(
            report_submitted_at=record.report.created_at,
            image_capture_time_known=False,
            image_capture_time=None,
            environmental_reference_time=context.requested_reference_time or context.requested_at,
            environmental_context_generated_at=context.generated_at,
            temporal_basis=assessment.temporal_basis,
        ),
        evidence=EventEvidence(
            report_id=record.report.id,
            is_synthetic=record.report.is_synthetic,
            citizen_evidence_summary=(
                "Structured visual interpretation; raw image and citizen text omitted."
            ),
            gemini=record.analysis,
            source_statuses=[
                EventSourceStatus(**{k: s[k] for k in ("provider", "status", "retrieved_at")})
                for s in statuses
            ],
            rules=[EventRule(**r.model_dump(exclude={"inputs_used"})) for r in assessment.rules],
            air_quality=context.air_quality,
            weather=context.weather,
            fires=context.fires,
            fire_search_radius_km=context.fire_search_radius_km,
            satellite=[
                SatelliteEvidence(
                    **p.model_dump(
                        include={
                            "product",
                            "status",
                            "availability",
                            "collection",
                            "band",
                            "unit",
                            "observation",
                        }
                    )
                )
                for p in context.satellite.products
            ]
            if context.satellite
            else None,
            assessment_provenance=assessment.provenance,
            source_snapshot_sha256=case.snapshot.evidence_sha256,
        ),
        forecast=EventForecast(
            **forecast.model_dump(
                include={
                    "provider",
                    "retrieved_at",
                    "issued_at",
                    "summaries",
                    "hourly_forecasts",
                    "provenance",
                    "independence_note",
                }
            ),
            status=forecast.provider_status.status,
        )
        if forecast
        else None,
        limitations=[
            *assessment.limitations,
            "Simulated handoff only; no government system or authority receives this packet.",
            "Origin and destination are manually selected prototype control rooms, "
            "not verified location ownership.",
            "Jurisdiction lookup is non-authoritative; "
            "no boundary proximity or causality is inferred.",
            "SHA-256 establishes byte integrity, not identity, authenticity or non-repudiation.",
            "Frozen observations and forecast may be stale; "
            "destination receipt does not refresh evidence.",
        ],
        handoff_id=handoff_id,
        handoff_created_at=now,
        simulated=True,
    )
