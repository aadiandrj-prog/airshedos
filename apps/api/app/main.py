import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.access.router import router as access_router
from app.access.runtime import ProtectedAccessLog, configured_access
from app.access.service import AccessService
from app.authority.router import router as authority_router
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
from app.operations.readiness import ReadinessRead
from app.persistence.contracts import (
    AccessDenied,
    Conflict,
    Gone,
    NotFound,
    PersistenceError,
    RateLimited,
    RecoveryUnavailable,
)
from app.persistence.repository import DurableRepository
from app.repository import IncidentRepository
from app.resident.router import ResidentUploadLimit
from app.resident.router import router as resident_router
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
    persistence: DurableRepository | None = None,
    access: AccessService | None = None,
    mode: str | None = None,
) -> FastAPI:
    selected_mode = mode or os.getenv("APP_MODE", "prototype")
    if selected_mode not in {"prototype", "pilot"}:
        raise ValueError("APP_MODE must be prototype or pilot")
    if selected_mode == "prototype":
        if access is not None or any(
            os.getenv(k)
            for k in (
                "DATABASE_URL",
                "SESSION_DATABASE_URL",
                "SEVA_WORKER_DATABASE_URL",
                "SEVA_CLEANUP_DATABASE_URL",
                "SEVA_RECOVERY_EPOCH",
                "S3_ACCESS_KEY_ID",
                "S3_SECRET_ACCESS_KEY",
            )
        ):
            raise ValueError("Synthetic prototype refuses pilot/private configuration")
        if environment is None and any(
            os.getenv(k)
            for k in (
                "GOOGLE_MAPS_PLATFORM_API_KEY",
                "NASA_FIRMS_MAP_KEY",
                "GOOGLE_CLOUD_PROJECT",
                "EARTH_ENGINE_PROJECT",
                "GOOGLE_API_KEY",
                "GEMINI_API_KEY",
            )
        ):
            raise ValueError("Synthetic prototype refuses live provider credentials")
    owned_engine = None
    if access is None and selected_mode == "pilot":
        try:
            access, owned_engine = configured_access()
        except (ValueError, KeyError, SQLAlchemyError):
            access = None  # Unconfigured pilot stays closed; legacy routes also remain blocked.

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
                if selected_mode == "pilot":
                    settings = settings.model_copy(
                        update={
                            "cache_ttl_seconds": min(settings.cache_ttl_seconds, 900),
                            "forecast_cache_ttl_seconds": min(
                                settings.forecast_cache_ttl_seconds, 900
                            ),
                        }
                    )
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
            if owned_engine is not None:
                owned_engine.dispose()

    api = FastAPI(
        title="AirshedOS API",
        version="0.11.0",
        lifespan=lifespan,
        description="Authenticated resident pilot intake and unit-scoped access. "
        "Legacy prototype handoffs remain simulated. No causal attribution or government delivery.",
    )
    api.include_router(environment_router)
    api.include_router(citizen_router)
    api.include_router(corroboration_router)
    api.include_router(review_router)
    api.include_router(handoff_router)
    api.include_router(access_router)
    api.include_router(resident_router)
    api.include_router(authority_router)
    api.add_middleware(ResidentUploadLimit)
    api.add_middleware(CitizenUploadLimit)

    @api.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        if request.url.path.startswith("/api/v2"):
            return JSONResponse({"detail": "Invalid request"}, status_code=422)
        if request.url.path == PATH:
            return invalid(
                "Provide one image, valid coordinates and description up to 2,000 characters."
            )
        return await request_validation_exception_handler(request, exc)

    api.state.repository = IncidentRepository()
    # Internal DI only: no new routes, implicit DB connection or migration at startup.
    # Phase 2 must provide verified identity/session isolation before v2 HTTP exposure.
    api.state.persistence = persistence
    api.state.access = access
    api.state.mode = selected_mode
    logging.getLogger("uvicorn.access").addFilter(ProtectedAccessLog())

    @api.middleware("http")
    async def pilot_boundary(request: Request, call_next):
        started = time.perf_counter()
        path = request.url.path
        if selected_mode == "pilot" and path.startswith("/api/v1"):
            response = JSONResponse({"detail": "Not found"}, status_code=404)
        else:
            response = await call_next(request)
        if path.startswith("/api/v2") or selected_mode == "pilot":
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["Pragma"] = "no-cache"
            response.headers["X-Content-Type-Options"] = "nosniff"
        if path.startswith("/api/v2"):
            logging.getLogger("uvicorn.error").info(
                json.dumps(
                    {
                        "event": "protected_request",
                        "method": request.method,
                        "status": response.status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    }
                )
            )
        return response

    @api.exception_handler(NotFound)
    async def missing(_request, _exc):
        return JSONResponse({"detail": "Not found"}, status_code=404)

    @api.exception_handler(AccessDenied)
    async def denied(_request, _exc):
        return JSONResponse({"detail": "Access denied"}, status_code=403)

    @api.exception_handler(Conflict)
    async def conflict(_request, _exc):
        return JSONResponse({"detail": "Conflict; refresh before acting"}, status_code=409)

    @api.exception_handler(Gone)
    async def gone(_request, _exc):
        return JSONResponse({"detail": "No longer available"}, status_code=410)

    @api.exception_handler(RateLimited)
    async def limited(_request, _exc):
        return JSONResponse(
            {"detail": "Pilot admission limit reached"},
            status_code=429,
            headers={"Retry-After": "3600"},
        )

    @api.exception_handler(SQLAlchemyError)
    async def unavailable(_request, _exc):
        return JSONResponse({"detail": "Service unavailable"}, status_code=503)

    @api.exception_handler(RecoveryUnavailable)
    async def recovery_unavailable(_request, _exc):
        return JSONResponse(
            {"detail": "Pilot recovery checks are incomplete. Retry later."}, status_code=503
        )

    @api.exception_handler(PersistenceError)
    async def custody_unavailable(_request, _exc):
        return JSONResponse(
            {"detail": "Private storage unavailable; text reporting remains valid"}, status_code=503
        )

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

    @api.get("/ready", tags=["Operations"], response_model=ReadinessRead | dict[str, str])
    def ready(repository: Repository):
        if selected_mode == "pilot":
            from app.operations.readiness import pilot_readiness

            result = pilot_readiness(
                access,
                api.state.environment,
                api.state.citizen_analyzer,
                media_required=os.getenv("PILOT_MEDIA_REQUIRED", "1") != "0",
            )
            return JSONResponse(
                result.model_dump(mode="json"), status_code=200 if result.status == "ready" else 503
            )
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
