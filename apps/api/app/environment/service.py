import asyncio
import json
import logging
import time
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.environment.http import ProviderFailure
from app.environment.models import (
    EnvironmentalContext,
    EnvironmentalSources,
    EnvironmentalSourceStatus,
    EnvironmentalSourceStatuses,
    ProviderConfiguration,
    SatelliteAtmosphericContext,
    SatelliteSearchWindow,
    SourceState,
)
from app.environment.providers import AirQualityProvider, FireProvider, WeatherProvider
from app.environment.satellite import (
    GRID_SCALE_M,
    PRODUCTS,
    EarthEngineSentinel5PProvider,
    SatelliteProvider,
    SatelliteQuery,
    absent,
    source_provenance,
)
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
        satellite: SatelliteProvider | None = None,
    ):
        self.providers = {"air_quality": air_quality, "weather": weather, "fires": fires}
        self.settings, self.clock = settings, clock
        self.satellite = satellite or EarthEngineSentinel5PProvider(
            settings.earth_engine_project, settings.satellite_timeout_seconds
        )
        self.satellite_lock = asyncio.Lock()
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
                key = (
                    name,
                    lat,
                    lng,
                    self.settings.firms_radius_km if name == "fires" else None,
                    self.settings.firms_dataset if name == "fires" else None,
                )
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
                                self._store(key, result, ttl)
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

    def _store(self, key, result, ttl):
        self._drop(key)
        self.cache[key] = (self.clock() + ttl, deepcopy(result))
        self.expiry_handles[key] = asyncio.get_running_loop().call_later(ttl, self._drop, key)
        while len(self.cache) > self.settings.cache_max_entries:
            self._drop(next(iter(self.cache)))

    async def satellite_context(self, lat, lng, at=None, lookback_hours=None):
        requested = datetime.now(UTC)
        end = at or requested.replace(minute=0, second=0, microsecond=0)
        hours = (
            lookback_hours if lookback_hours is not None else self.settings.satellite_lookback_hours
        )
        window = SatelliteSearchWindow(
            start=end - timedelta(hours=hours),
            end=end,
            lookback_hours=hours,
            end_mode="explicit" if at else "current_hour",
        )
        query = SatelliteQuery(
            round(lat, 4), round(lng, 4), window, self.settings.satellite_radius_km
        )
        key = (
            "satellite",
            query.latitude,
            query.longitude,
            window.start.isoformat(),
            window.end.isoformat(),
            query.radius_km,
            tuple(PRODUCTS),
        )
        started = time.perf_counter()

        def assemble(products, state, message):
            now = datetime.now(UTC)
            count = sum(p.observation is not None for p in products)
            return SatelliteAtmosphericContext(
                latitude=lat,
                longitude=lng,
                query_latitude=query.latitude,
                query_longitude=query.longitude,
                requested_at=requested,
                generated_at=now,
                search_window=window,
                retrieval_radius_km=query.radius_km,
                grid_scale_m=GRID_SCALE_M,
                products=products,
                availability="complete" if count == 3 else "partial" if count else "none",
                provider_status=EnvironmentalSourceStatus(
                    provider=self.satellite.name,
                    configured=self.satellite.configured,
                    status=state,
                    message=message,
                    retrieved_at=now if state == SourceState.LIVE else None,
                    latency_ms=round((time.perf_counter() - started) * 1000, 2),
                ),
                provenance=source_provenance(),
            )

        async def retrieve():
            async with self.satellite_lock:
                cached = self.cache.get(key)
                if cached and cached[0] > self.clock():
                    self.cache.move_to_end(key)
                    result = deepcopy(cached[1].data)
                    result.latitude, result.longitude = lat, lng
                    result.requested_at, result.generated_at = requested, datetime.now(UTC)
                    result.provider_status.status = SourceState.CACHED
                    result.provider_status.message = (
                        "Cached satellite search; original retrieval "
                        "and acquisition times retained."
                    )
                    for product in result.products:
                        product.cache_hit = True
                        if product.observation:
                            product.status = SourceState.CACHED
                            product.observation.age_seconds = max(
                                0,
                                (
                                    result.generated_at - product.observation.observed_at
                                ).total_seconds(),
                            )
                    return result
                self._drop(key)
                products = await self.satellite.fetch(query)
                if len(products) != 3 or {p.product for p in products} != set(PRODUCTS):
                    raise ValueError("Incomplete satellite product response")
                successful = any(
                    p.availability
                    in ("available", "no_scene", "quality_filtered", "no_usable_pixels")
                    for p in products
                )
                state = (
                    SourceState.LIVE
                    if successful
                    else SourceState.NOT_CONFIGURED
                    if all(p.status == SourceState.NOT_CONFIGURED for p in products)
                    else SourceState.ERROR
                    if any(p.status == SourceState.ERROR for p in products)
                    else SourceState.UNAVAILABLE
                )
                result = assemble(
                    products,
                    state,
                    (
                        "Fresh search; acquisition times and availability are per product."
                        if successful
                        else products[0].message
                    ),
                )
                # Cache genuine absence/QA results, but never provider/auth errors.
                if (
                    all(
                        p.availability
                        in ("available", "no_scene", "quality_filtered", "no_usable_pixels")
                        for p in products
                    )
                    and self.settings.satellite_cache_ttl_seconds > 0
                ):
                    self._store(
                        key,
                        ProviderResult(result, result.provider_status),
                        self.settings.satellite_cache_ttl_seconds,
                    )
                return result

        try:
            result = await asyncio.wait_for(retrieve(), self.settings.satellite_timeout_seconds + 1)
        except TimeoutError:
            result = assemble(
                [
                    absent(
                        p,
                        SourceState.UNAVAILABLE,
                        "timeout",
                        "Satellite request deadline exceeded.",
                    )
                    for p in PRODUCTS
                ],
                SourceState.UNAVAILABLE,
                "Satellite request deadline exceeded; ground sources remain independent.",
            )
        except Exception:
            result = assemble(
                [
                    absent(
                        p,
                        SourceState.ERROR,
                        "provider_error",
                        "Satellite result could not be normalized.",
                    )
                    for p in PRODUCTS
                ],
                SourceState.ERROR,
                "Satellite result could not be normalized.",
            )
        result.provider_status.latency_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            json.dumps(
                {
                    "event": "environment_provider",
                    "provider": self.satellite.name,
                    "success": result.provider_status.status
                    in (SourceState.LIVE, SourceState.CACHED),
                    "status": result.provider_status.status,
                    "latency_ms": result.provider_status.latency_ms,
                }
            )
        )
        return result

    async def context(
        self,
        lat: float,
        lng: float,
        at: datetime | None = None,
        include_satellite: bool = True,
        lookback_hours: int | None = None,
    ) -> EnvironmentalContext:
        requested_at = datetime.now(UTC)

        async def satellite_result():
            return (
                await self.satellite_context(lat, lng, at, lookback_hours)
                if include_satellite
                else None
            )

        aq, weather, fires, satellite = await asyncio.gather(
            *(self._bounded_result(name, lat, lng) for name in ("air_quality", "weather", "fires")),
            satellite_result(),
        )
        return EnvironmentalContext(
            latitude=lat,
            longitude=lng,
            requested_at=requested_at,
            generated_at=datetime.now(UTC),
            requested_reference_time=at,
            satellite=satellite,
            air_quality=aq.data,
            weather=weather.data,
            fires=fires.data,
            fire_search_radius_km=self.settings.firms_radius_km,
            fire_window_days=2,
            fire_dataset=self.settings.firms_dataset,
            source_statuses=EnvironmentalSourceStatuses(
                air_quality=aq.source, weather=weather.source, fires=fires.source
            ),
        )
