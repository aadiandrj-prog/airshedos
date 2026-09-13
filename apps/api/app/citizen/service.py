import asyncio
import logging
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from app.citizen.models import (
    DISCLAIMER,
    PROMPT_VERSION,
    AnalysisStatus,
    CitizenAnalysisResponse,
    CitizenVisualSignal,
    GeminiEvidenceAnalysis,
    ModelProvenance,
)
from app.citizen.provider import AnalysisFailure, CitizenEvidenceAnalyzer
from app.models import CitizenReport, EvidenceStatus, SignalType

logger = logging.getLogger(__name__)
MESSAGES = {
    AnalysisStatus.INTERPRETED: DISCLAIMER,
    AnalysisStatus.NOT_CONFIGURED: "Gemini is not configured. No interpretation ran.",
    AnalysisStatus.AUTH_ERROR: "Check Vertex authentication, permissions and API enablement.",
    AnalysisStatus.MODEL_UNAVAILABLE: "Configured Gemini model unavailable in this location.",
    AnalysisStatus.QUOTA_LIMITED: "Vertex quota or rate limit reached. Please try again later.",
    AnalysisStatus.TIMEOUT: "Gemini exceeded the request deadline. No interpretation is available.",
    AnalysisStatus.SAFETY_BLOCKED: "The model safety filter blocked this image or context.",
    AnalysisStatus.INVALID_RESPONSE: "Gemini returned an invalid visual interpretation.",
    AnalysisStatus.ERROR: "Gemini could not complete this request. Please try again later.",
}


async def interpret(analyzer: CitizenEvidenceAnalyzer, image, mime_type, latitude, longitude, text):
    started = perf_counter()
    request_id = str(uuid4())
    report = CitizenReport(
        id=f"CR-{uuid4()}",
        created_at=datetime.now(UTC),
        latitude=latitude,
        longitude=longitude,
        description=text,
        language="und",  # No language detection/translation in Phase 2A.
    )
    result = CitizenAnalysisResponse(
        request_id=request_id,
        status=AnalysisStatus.ERROR,
        report=report,
        message=MESSAGES[AnalysisStatus.ERROR],
        latency_ms=0,
    )
    try:
        async with asyncio.timeout(analyzer.settings.timeout_seconds):
            raw = await analyzer.analyze(image, mime_type, latitude, longitude, text)
        generated = datetime.now(UTC)
        provenance = ModelProvenance(
            source_id=report.id,
            source_report_id=report.id,
            method="vertex_ai_gemini_multimodal",
            is_demo=False,
            note="Derived visual interpretation. Upload time is not image acquisition time. "
            "No environmental corroboration or source attribution has occurred.",
            model=analyzer.settings.model,
            model_version=raw.model_version,
            generated_at=generated,
        )
        result.analysis = GeminiEvidenceAnalysis(
            **raw.interpretation.model_dump(),
            source_report_id=report.id,
            analyzed_at=generated,
            provenance=provenance,
        )
        result.evidence = CitizenVisualSignal(
            id=f"CE-{uuid4()}",
            signal_type=SignalType.CITIZEN_REPORT,
            source="gemini_multimodal",
            status=EvidenceStatus.INTERPRETED,
            interpretation_at=generated,
            source_report_id=report.id,
            summary="Possible event type: "
            f"{raw.interpretation.event_type.value.replace('_', ' ')}. "
            "Visual evidence only; requires environmental corroboration.",
            provenance=provenance,
            raw_reference=report.id,
        )
        result.status = AnalysisStatus.INTERPRETED
    except AnalysisFailure as exc:
        result.status = exc.status
    except TimeoutError:
        result.status = AnalysisStatus.TIMEOUT
    except Exception:
        result.status = AnalysisStatus.ERROR
    if result.status != AnalysisStatus.INTERPRETED:
        result.analysis = result.evidence = None
    result.message = MESSAGES[result.status]
    result.latency_ms = round((perf_counter() - started) * 1000, 2)
    logger.info(
        "citizen_analysis request_id=%s model=%s prompt_version=%s status=%s "
        "event_class=%s latency_ms=%.2f",
        request_id,
        analyzer.settings.model,
        PROMPT_VERSION,
        result.status,
        result.analysis.event_type if result.analysis else "none",
        result.latency_ms,
    )
    return result
