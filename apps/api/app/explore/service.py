"""Reuse provider normalization with task-local, shared PostgreSQL admission."""

import math
from datetime import UTC, datetime, timedelta

from pydantic import AwareDatetime, Field
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.access.limits import charge
from app.environment.forecast_models import AirQualityForecastContext
from app.environment.http import ProviderFailure, request_admission
from app.environment.models import EnvironmentalContext, SourceState
from app.environment.service import EnvironmentService, ProviderResult
from app.models import DomainModel
from app.persistence.contracts import RateLimited


class Area(DomainModel):
    id: str
    name: str
    latitude: float
    longitude: float
    note: str = "Representative area point, not your device or a report location."


AREAS = {
    a.id: a
    for a in (
        Area(id="delhi", name="New Delhi", latitude=28.6139, longitude=77.2090),
        Area(id="gurugram", name="Gurugram", latitude=28.4595, longitude=77.0266),
        Area(id="noida", name="Noida", latitude=28.5355, longitude=77.3910),
    )
}


def approximate_area(latitude: float, longitude: float) -> Area:
    # Match the browser grid, but enforce it again for direct API clients. No raw
    # device coordinates enter provider caches, source queries or response models.
    return Area(
        id="nearby",
        name="Near you",
        latitude=math.floor(latitude * 200 + 0.5) / 200,
        longitude=math.floor(longitude * 200 + 0.5) / 200,
        note="Approximate 0.005 degree grid (about 550m north-south). "
        "Device accuracy and provider resolution vary; this is not a local sensor reading.",
    )


class Overview(DomainModel):
    area: Area
    context: EnvironmentalContext
    forecast: AirQualityForecastContext
    returned_fire_count: int = Field(ge=0)
    fires_truncated: bool
    expires_at: AwareDatetime
    notice: str = (
        "Area context, not a regulatory monitoring station or evidence of a local violation. "
        "Forecast is a separate provider outlook. "
        "Missing fire detections do not rule out pollution."
    )


class OverviewService:
    def __init__(self, environment, repo, *, daily_limit=100, requests_per_hour=120):
        self.repo, self.daily_limit, self.requests_per_hour = repo, daily_limit, requests_per_hour
        # Separate fixed-area caches; never reuse case/report context or retained evidence.
        settings = environment.settings.model_copy(
            update={
                "cache_ttl_seconds": min(environment.settings.cache_ttl_seconds, 900),
                "forecast_cache_ttl_seconds": min(
                    environment.settings.forecast_cache_ttl_seconds, 900
                ),
                "firms_cache_ttl_seconds": min(environment.settings.firms_cache_ttl_seconds, 900),
                "cache_max_entries": 32,
            }
        )
        self.environment = EnvironmentService(
            environment.providers["air_quality"],
            environment.providers["weather"],
            environment.providers["fires"],
            settings,
            forecast=environment.forecast,
        )

    def admit_view(self):
        with self.repo.sessions.begin() as session:
            charge(
                session,
                scope="global",
                rule="PUBLIC_OVERVIEW",
                period="hour",
                maximum=self.requests_per_hour,
            )

    async def admit_network(self, url):
        def reserve():
            with self.repo.sessions.begin() as session:
                charge(
                    session,
                    scope="global",
                    rule="PUBLIC_PROVIDER_HTTP",
                    period="day",
                    maximum=self.daily_limit,
                )
                # Google public requests share the application's existing paid-call budget.
                if url.startswith(
                    ("https://airquality.googleapis.com/", "https://weather.googleapis.com/")
                ):
                    charge(
                        session,
                        scope="global",
                        rule="PAID_ANALYSIS",
                        period="day",
                        maximum=self.repo.limits.provider_calls_per_day,
                    )

        try:
            await run_in_threadpool(reserve)
        except RateLimited:
            raise ProviderFailure(
                SourceState.UNAVAILABLE, "Shared daily provider budget reached. Try later."
            ) from None
        except SQLAlchemyError:
            raise ProviderFailure(
                SourceState.UNAVAILABLE, "Provider admission is temporarily unavailable."
            ) from None

    async def overview(self, area_id: str | Area):
        area = AREAS[area_id] if isinstance(area_id, str) else area_id
        await run_in_threadpool(self.admit_view)
        token = request_admission.set(self.admit_network)
        try:
            env = self.environment
            # No satellite, Gemini, geocoder, device location or case access on this path.
            context = await env.context(area.latitude, area.longitude, include_satellite=False)
            current = ProviderResult(context.air_quality, context.source_statuses.air_quality)
            forecast = await env.forecast_context(
                area.latitude, area.longitude, current_result=current
            )
        finally:
            request_admission.reset(token)
        count = len(context.fires) if context.fires is not None else 0
        if context.fires is not None:
            context.fires = context.fires[:50]
        now = datetime.now(UTC)
        deadlines = [now + timedelta(minutes=15)]
        for name, source in context.source_statuses:
            if source.retrieved_at:
                ttl = (
                    env.settings.firms_cache_ttl_seconds
                    if name == "fires"
                    else env.settings.cache_ttl_seconds
                )
                deadlines.append(source.retrieved_at + timedelta(seconds=ttl))
        if forecast.retrieved_at:
            deadlines.append(
                forecast.retrieved_at + timedelta(seconds=env.settings.forecast_cache_ttl_seconds)
            )
        return Overview(
            area=area,
            context=context,
            forecast=forecast,
            returned_fire_count=count,
            fires_truncated=count > 50,
            expires_at=min(deadlines),
        )
