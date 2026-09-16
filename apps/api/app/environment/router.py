from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import AwareDatetime

from app.environment.forecast_models import AirQualityForecastContext
from app.environment.models import (
    EnvironmentalContext,
    EnvironmentalSources,
    SatelliteAtmosphericContext,
)
from app.environment.service import EnvironmentService

router = APIRouter(prefix="/api/v1/environment", tags=["Environmental context"])


def get_environment(request: Request) -> EnvironmentService:
    return request.app.state.environment


Environment = Annotated[EnvironmentService, Depends(get_environment)]


@router.get("/sources", response_model=EnvironmentalSources)
def sources(environment: Environment):
    """Configuration presence only; no network call or credential disclosure."""
    return environment.sources()


@router.get("/context", response_model=EnvironmentalContext)
async def context(
    environment: Environment,
    lat: Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)],
    lng: Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)],
    include_satellite: bool = True,
    lookback_hours: Annotated[int | None, Query(ge=1, le=168)] = None,
    at: Annotated[
        AwareDatetime | None,
        Query(
            description=(
                "Optional reference time. "
                "Ground providers still query current conditions. "
                "Satellite uses this as its window end. Include a timezone."
            )
        ),
    ] = None,
):
    """Independent environmental context; never corroborates the fictional demo incident."""
    return await environment.context(lat, lng, at, include_satellite, lookback_hours)


@router.get("/satellite", response_model=SatelliteAtmosphericContext)
async def satellite_context(
    environment: Environment,
    lat: Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)],
    lng: Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)],
    at: AwareDatetime | None = None,
    lookback_hours: Annotated[int | None, Query(ge=1, le=168)] = None,
):
    """Independent bounded satellite lookup; lets the UI show ground data without waiting."""
    return await environment.satellite_context(lat, lng, at, lookback_hours)


@router.get("/forecast", response_model=AirQualityForecastContext)
async def forecast_context(
    environment: Environment,
    lat: Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)],
    lng: Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)],
    horizon_hours: Annotated[
        int, Query(description="6, 12 or 24 hours; default includes all summaries")
    ] = 24,
):
    """Google provider outlook. Never independent corroboration or an AirshedOS prediction."""
    if horizon_hours not in (6, 12, 24):
        raise HTTPException(422, "Forecast horizon must be 6, 12 or 24 hours.")
    return await environment.forecast_context(lat, lng, horizon_hours)
