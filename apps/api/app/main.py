import os
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.citizen.provider import CitizenEvidenceAnalyzer, GeminiCitizenEvidenceAnalyzer
from app.citizen.router import PATH, CitizenUploadLimit, invalid
from app.citizen.router import router as citizen_router
from app.citizen.settings import CitizenSettings
from app.corroboration.repository import EphemeralReportRepository
from app.corroboration.router import router as corroboration_router
from app.corroboration.settings import CorroborationSettings
from app.environment.forecast import GoogleAirQualityForecastProvider
from app.environment.http import ProviderHTTP
from app.environment.providers import (
    GoogleAirQualityProvider,
    GoogleWeatherProvider,
    NasaFirmsProvider,
)
from app.environment.router import router as environment_router
from app.environment.service import EnvironmentService
from app.environment.settings import EnvironmentSettings
from app.handoff.repository import HandoffRepository
from app.handoff.router import router as handoff_router
from app.models import PollutionIncident, ShareRequest, ShareResponse
from app.repository import IncidentRepository
from app.review.repository import OfficerCaseRepository
from app.review.router import router as review_router


def get_repository(request: Request) -> IncidentRepository:
    return request.app.state.repository


Repository = Annotated[IncidentRepository, Depends(get_repository)]


def create_app(
    environment: EnvironmentService | None = None,
    citizen_analyzer: CitizenEvidenceAnalyzer | None = None,
    structured_reports: EphemeralReportRepository | None = None,
    corroboration_settings: CorroborationSettings | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(api: FastAPI):
        api.state.citizen_analyzer = citizen_analyzer or GeminiCitizenEvidenceAnalyzer(
            CitizenSettings.from_env()
        )
        api.state.corroboration_settings = (
            corroboration_settings or CorroborationSettings.from_env()
        )
        api.state.structured_reports = structured_reports or EphemeralReportRepository(
            api.state.corroboration_settings
        )
        api.state.officer_cases = OfficerCaseRepository()
        api.state.handoffs = HandoffRepository()
        try:
            if environment is not None:
                api.state.environment = environment
                yield
            else:
                settings = EnvironmentSettings.from_env()
                async with httpx.AsyncClient(follow_redirects=False) as client:
                    http = ProviderHTTP(client, settings.timeout_seconds)
                    api.state.environment = EnvironmentService(
                        GoogleAirQualityProvider(http, settings.google_key.get_secret_value()),
                        GoogleWeatherProvider(http, settings.google_key.get_secret_value()),
                        NasaFirmsProvider(
                            http,
                            settings.firms_key.get_secret_value(),
                            settings.firms_radius_km,
                            settings.firms_dataset,
                        ),
                        settings,
                        forecast=GoogleAirQualityForecastProvider(
                            http, settings.google_key.get_secret_value()
                        ),
                    )
                    yield
        finally:
            api.state.structured_reports.clear()
            api.state.officer_cases.clear()
            api.state.handoffs.clear()

    api = FastAPI(
        title="AirshedOS API",
        version="0.8.0",
        lifespan=lifespan,
        description="Phase 3B. Simulated jurisdiction handoff and PollutionEvent v1. "
        "No causal attribution. Demo incident sharing is simulated.",
    )
    api.include_router(environment_router)
    api.include_router(citizen_router)
    api.include_router(corroboration_router)
    api.include_router(review_router)
    api.include_router(handoff_router)
    api.add_middleware(CitizenUploadLimit)

    @api.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        if request.url.path == PATH:
            return invalid(
                "Provide one image, valid coordinates and description up to 2,000 characters."
            )
        return await request_validation_exception_handler(request, exc)

    api.state.repository = IncidentRepository()
    api.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000,https://airshedos.vercel.app",
            ).split(",")
            if origin.strip()
        ],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @api.get("/health", tags=["Operations"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/ready", tags=["Operations"])
    def ready(repository: Repository) -> dict[str, str]:
        if not repository.list():
            raise HTTPException(503, "Demo repository is not ready")
        return {"status": "ready", "storage": "in_memory", "data_mode": "demo"}

    @api.get("/api/v1/incidents", response_model=list[PollutionIncident], tags=["Incidents"])
    def list_incidents(repository: Repository):
        return repository.list()

    @api.get(
        "/api/v1/incidents/{incident_id}", response_model=PollutionIncident, tags=["Incidents"]
    )
    def incident_detail(incident_id: str, repository: Repository):
        try:
            return repository.get(incident_id)
        except KeyError as exc:
            raise HTTPException(404, "Incident not found") from exc

    @api.post(
        "/api/v1/incidents/{incident_id}/acknowledge",
        response_model=PollutionIncident,
        tags=["Actions"],
    )
    def acknowledge(incident_id: str, repository: Repository):
        try:
            return repository.acknowledge(incident_id)
        except KeyError as exc:
            raise HTTPException(404, "Incident not found") from exc

    @api.post(
        "/api/v1/incidents/{incident_id}/share", response_model=ShareResponse, tags=["Actions"]
    )
    def share(incident_id: str, payload: ShareRequest, repository: Repository):
        try:
            return repository.share(incident_id, payload.target_jurisdiction_id)
        except KeyError as exc:
            raise HTTPException(404, "Incident not found") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    return api


app = create_app()
