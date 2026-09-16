import re

from fastapi import APIRouter, HTTPException, Request

from app.corroboration.engine import assess
from app.corroboration.models import CorroborationAssessment, ReportUnavailable
from app.environment.service import ProviderResult

router = APIRouter(tags=["Citizen evidence"])


@router.post(
    "/api/v1/citizen-reports/{report_id}/corroborate",
    response_model=CorroborationAssessment,
    responses={404: {"model": ReportUnavailable}},
)
async def corroborate(report_id: str, request: Request):
    # No browser-owned analysis, coordinates, text or image is accepted here.
    async for chunk in request.stream():
        if chunk:
            raise HTTPException(
                422, "This endpoint accepts a report ID only, with no request body."
            )
    if not re.fullmatch(
        r"CR-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", report_id
    ):
        raise HTTPException(404, ReportUnavailable().detail)
    record = request.app.state.structured_reports.get(report_id)
    if record is None:
        raise HTTPException(404, ReportUnavailable().detail)
    context = await request.app.state.environment.context(
        record.report.latitude,
        record.report.longitude,
        at=record.report.created_at,
        include_satellite=True,
    )
    assessment = assess(record, context, request.app.state.corroboration_settings)
    # The frozen checklist runs BEFORE this separate provider outlook. It never sees forecasts.
    assessment.forecast_outlook = await request.app.state.environment.forecast_context(
        record.report.latitude,
        record.report.longitude,
        current_result=ProviderResult(context.air_quality, context.source_statuses.air_quality),
    )
    request.app.state.officer_cases.add(
        record, assessment, request.app.state.structured_reports.remaining_ttl(report_id)
    )
    return assessment
