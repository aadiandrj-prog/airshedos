import asyncio
import json
import logging
import time
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime

from app.environment.http import ProviderFailure
from app.environment.models import (
    EnvironmentalContext,
    EnvironmentalSources,
    EnvironmentalSourceStatus,
    EnvironmentalSourceStatuses,
    ProviderConfiguration,
    SourceState,
)
from app.environment.providers import AirQualityProvider, FireProvider, WeatherProvider
from app.environment.settings import EnvironmentSettings

logger = logging.getLogger("airshedos.environment")
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.propagate = False


@dataclass
class ProviderResult:
    data: object
    source: EnvironmentalSourceStatus


class EnvironmentService:
    def __init__(
        self,
        air_quality: AirQualityProvider,
        weather: WeatherProvider,
        fires: FireProvider,
        settings: EnvironmentSettings,
        clock=time.monotonic,
    ):
        self.providers = {"air_quality": air_quality, "weather": weather, "fires": fires}
        self.settings, self.clock = settings, clock
        self.cache: OrderedDict[tuple, tuple[float, ProviderResult]] = OrderedDict()
        self.expiry_handles: dict[tuple, asyncio.TimerHandle] = {}
        # Three bounded locks coalesce same-point requests and limit quota pressure.
        self.locks = {key: asyncio.Lock() for key in self.providers}

    def _drop(self, key: tuple) -> None:
        self.cache.pop(key, None)
        handle = self.expiry_handles.pop(key, None)
        if handle is not None:
            handle.cancel()

    async def _bounded_result(self, name: str, lat: float, lng: float) -> ProviderResult:
        started = time.perf_counter()
        try:
            return await asyncio.wait_for(
                self._result(name, lat, lng), self.settings.timeout_seconds * 2 + 1
            )
        except TimeoutError:
            source = EnvironmentalSourceStatus(
                provider=self.providers[name].name,
                configured=self.providers[name].configured,
                status=SourceState.UNAVAILABLE,
                message="Provider request deadline exceeded. Try again later.",
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
            )
            logger.info(
                json.dumps(
                    {
                        "event": "environment_provider",
                        "provider": source.provider,
                        "success": False,
                        "status": source.status,
                        "latency_ms": source.latency_ms,
                    }
                )
            )
            return ProviderResult(None, source)

    def sources(self) -> EnvironmentalSources:
        return EnvironmentalSources(
            **{
                name: ProviderConfiguration(
                    provider=provider.name,
                    configured=provider.configured,
                    configuration_state="configured" if provider.configured else "not_configured",
                )
                for name, provider in self.providers.items()
            }
        )

    async def _result(self, name: str, lat: float, lng: float) -> ProviderResult:
        started = time.perf_counter()
        provider = self.providers[name]
        result = ProviderResult(
            None,
            EnvironmentalSourceStatus(
                provider=provider.name,
                configured=provider.configured,
                status=SourceState.NOT_CONFIGURED,
                message="Backend provider credentials are not configured.",
                latency_ms=0,
            ),
        )
        if provider.configured:
            async with self.locks[name]:
                # Exact validated float coordinates: no reuse across distinct geographic points.
                key = (name, lat, lng, self.settings.firms_radius_km if name == "fires" else None)
                cached = self.cache.get(key)
                if cached and cached[0] > self.clock():
                    self.cache.move_to_end(key)
                    result = deepcopy(cached[1])
                    result.source.status = SourceState.CACHED
                    result.source.message = (
                        "Cached response; original observation and retrieval times retained."
                    )
                    observations = result.data if isinstance(result.data, list) else [result.data]
                    for observation in observations:
                        if observation is not None:
                            observation.status = SourceState.CACHED
                else:
                    self._drop(key)
                    try:
                        data = await provider.fetch(lat, lng)
                        retrieved = datetime.now(UTC)
                        state = SourceState.LIVE if data is not None else SourceState.UNAVAILABLE
                        result = ProviderResult(
                            data,
                            EnvironmentalSourceStatus(
                                provider=provider.name,
                                configured=True,
                                status=state,
                                message=(
                                    "Current response. Observation times may differ."
                                    if data is not None
                                    else "No usable observations for this location."
                                ),
                                retrieved_at=retrieved,
                                latency_ms=0,
                            ),
                        )
                        if data is not None:
                            ttl = (
                                self.settings.firms_cache_ttl_seconds
                                if name == "fires"
                                else self.settings.cache_ttl_seconds
                            )
                            if ttl > 0:
                                self.cache[key] = (self.clock() + ttl, deepcopy(result))
                                self.expiry_handles[key] = asyncio.get_running_loop().call_later(
                                    ttl, self._drop, key
                                )
                                while len(self.cache) > self.settings.cache_max_entries:
                                    self._drop(next(iter(self.cache)))
                    except ProviderFailure as exc:
                        result.source.status, result.source.message = exc.status, exc.message
                    except Exception:
                        # Never log exception strings, payloads, headers, or credential URLs.
                        result.source.status = SourceState.ERROR
                        result.source.message = (
                            "Provider response could not be normalized. No values were substituted."
                        )
        result.source.latency_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            json.dumps(
                {
                    "event": "environment_provider",
                    "provider": provider.name,
                    "success": result.source.status in (SourceState.LIVE, SourceState.CACHED),
                    "status": result.source.status,
                    "latency_ms": result.source.latency_ms,
                }
            )
        )
        return result

    async def context(
        self, lat: float, lng: float, at: datetime | None = None
    ) -> EnvironmentalContext:
        requested_at = datetime.now(UTC)
        aq, weather, fires = await asyncio.gather(
            *(self._bounded_result(name, lat, lng) for name in ("air_quality", "weather", "fires"))
        )
        return EnvironmentalContext(
            latitude=lat,
            longitude=lng,
            requested_at=requested_at,
            generated_at=datetime.now(UTC),
            requested_reference_time=at,
            air_quality=aq.data,
            weather=weather.data,
            fires=fires.data,
            fire_search_radius_km=self.settings.firms_radius_km,
            fire_window_days=2,
            source_statuses=EnvironmentalSourceStatuses(
                air_quality=aq.source, weather=weather.source, fires=fires.source
            ),
        )
