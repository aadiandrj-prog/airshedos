from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import AwareDatetime

from app.environment.models import EnvironmentalContext, EnvironmentalSources
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
    at: Annotated[
        AwareDatetime | None,
        Query(
            description=(
                "Optional reference time, preserved as metadata only. "
                "This phase always queries current "
                "conditions; no historical retrieval is performed. Include a timezone."
            )
        ),
    ] = None,
):
    """Independent environmental context; never corroborates the fictional demo incident."""
    return await environment.context(lat, lng, at)
