import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.environment.geo import EARTH_RADIUS_KM, bounding_boxes, haversine_km
from app.environment.http import ProviderFailure, ProviderHTTP
from app.environment.models import EnvironmentalContext, SourceState
from app.environment.providers import (
    GoogleAirQualityProvider,
    GoogleWeatherProvider,
    NasaFirmsProvider,
)
from app.environment.service import EnvironmentService, logger
from app.environment.settings import EnvironmentSettings
from app.main import create_app

FIXTURES = Path(__file__).parent / "fixtures"
LAT, LNG = 28.4595, 77.0266
TEST_KEY = "test-only-placeholder-never-a-real-key"


def provider_response(request):
    if "airquality" in request.url.host:
        return httpx.Response(
            200, json=json.loads((FIXTURES / "google_air_quality.json").read_text())
        )
    if "weather" in request.url.host:
        return httpx.Response(200, json=json.loads((FIXTURES / "google_weather.json").read_text()))
    return httpx.Response(200, text=(FIXTURES / "firms.csv").read_text())


def service(client, settings=None, clock=None):
    settings = settings or EnvironmentSettings(google_key=TEST_KEY, firms_key=TEST_KEY)
    http = ProviderHTTP(client, settings.timeout_seconds)
    return EnvironmentService(
        GoogleAirQualityProvider(http, settings.google_key.get_secret_value()),
        GoogleWeatherProvider(http, settings.google_key.get_secret_value()),
        NasaFirmsProvider(
            http,
            settings.firms_key.get_secret_value(),
            settings.firms_radius_km,
            settings.firms_dataset,
        ),
        settings,
        **({"clock": clock} if clock else {}),
    )


@pytest.mark.anyio
async def test_normalization_all_providers():
    requests = []

    def handler(request):
        requests.append(request)
        return provider_response(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await service(client).context(LAT, LNG)
    aq, weather, fires = result.air_quality, result.weather, result.fires
    assert [i.value for i in aq.indexes] == [68, 112]
    assert [i.code for i in aq.indexes] == ["uaqi", "ind_cpcb"]
    assert aq.indexes[0].dominant_pollutant == "pm25"
    assert aq.pollutants[0].concentration.unit == "MICROGRAMS_PER_CUBIC_METER"
    assert aq.pollutants[1].concentration.unit == "PARTS_PER_BILLION"
    assert aq.pollutants[2].concentration is None
    assert weather.temperature.value == 31.4
    assert weather.wind_from_degrees == 225
    assert weather.wind_speed.unit == "KILOMETERS_PER_HOUR"
    assert weather.sea_level_pressure.unit == "MILLIBARS"
    assert weather.precipitation_qpf.value == 0
    assert weather.precipitation_probability_percent == 0
    assert len(fires) == 2
    assert fires[0].distance_from_query_km == pytest.approx(1.112, abs=0.001)
    assert fires[0].confidence == "h"
    assert fires[0].observed_at.hour == 0 and fires[0].observed_at.minute == 5
    assert fires[0].brightness.unit == "KELVIN"
    assert fires[0].fire_radiative_power.unit == "MEGAWATTS"
    for observation in [aq, weather, *fires]:
        assert observation.observed_at.tzinfo and observation.retrieved_at.tzinfo
        assert observation.provenance.source_id and not observation.provenance.is_demo
        assert observation.status == SourceState.LIVE
    assert all(s.status == SourceState.LIVE for _, s in result.source_statuses)
    assert len(requests) == 3
    aq_request = next(r for r in requests if "airquality" in r.url.host)
    assert aq_request.headers["X-Goog-Api-Key"] == TEST_KEY
    assert "POLLUTANT_CONCENTRATION" in json.loads(aq_request.content)["extraComputations"]
    assert TEST_KEY not in result.model_dump_json()


@pytest.mark.parametrize(
    "coords,expected",
    [
        ((0, 0, 0, 0), 0),
        ((0, 0, 0, 1), 111.195),
        ((0, 179.9, 0, -179.9), 22.239),
        ((90, 0, 90, 120), 0),
        ((0, 0, 0, 180), EARTH_RADIUS_KM * 3.141592653589793),
        ((28.4595, 77.0266, 28.6139, 77.2090), 24.70),
    ],
)
def test_haversine(coords, expected):
    assert haversine_km(*coords) == pytest.approx(expected, abs=0.05)


@pytest.mark.parametrize(
    "lat,lng", [(0, 179.99), (0, -179.99), (89.99, 40), (-89.99, -40), (LAT, LNG)]
)
def test_bounding_boxes(lat, lng):
    boxes = bounding_boxes(lat, lng, 25)
    for west, south, east, north in boxes:
        assert -180 <= west < east <= 180
        assert -90 <= south < north <= 90
    if abs(lng) > 179:
        assert len(boxes) == 2
    if abs(lat) > 89:
        assert boxes[0][0] == -180 and boxes[0][2] == 180


@pytest.mark.anyio
@pytest.mark.parametrize(
    "status,expected,attempts",
    [
        (401, "error", 1),
        (403, "error", 1),
        (400, "error", 1),
        (404, "error", 1),
        (429, "unavailable", 2),
        (500, "unavailable", 2),
        (503, "unavailable", 2),
    ],
)
async def test_provider_http_failures_are_partial_and_secret_safe(status, expected, attempts):
    calls = 0

    def handler(request):
        nonlocal calls
        if "weather" in request.url.host:
            calls += 1
            return httpx.Response(status, text=f"Provider error {TEST_KEY}")
        return provider_response(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        context = await service(client).context(LAT, LNG)
    assert context.source_statuses.weather.status == expected
    assert context.weather is None and context.air_quality and context.fires
    assert calls == attempts and TEST_KEY not in context.model_dump_json()


@pytest.mark.anyio
async def test_timeout_retries_are_bounded():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout(f"secret URL: {TEST_KEY}")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        context = await service(client).context(LAT, LNG)
    assert calls == 6
    assert all(s.status == "unavailable" for _, s in context.source_statuses)
    assert context.air_quality is None and context.weather is None and context.fires is None
    assert TEST_KEY not in context.model_dump_json()


@pytest.mark.anyio
async def test_retry_recovers_transient_response():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(503) if calls == 1 else provider_response(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        observation = await GoogleWeatherProvider(ProviderHTTP(client, 8), TEST_KEY).fetch(LAT, LNG)
    assert calls == 2 and observation.temperature.value == 31.4


@pytest.mark.anyio
@pytest.mark.parametrize(
    "payload",
    [
        "bad JSON",
        "[]",
        '{"temperature":1}',
        '{"temperature":{"degrees":31,"unit":"CELSIUS"},"currentTime":"invalid"}',
    ],
)
async def test_malformed_payload(payload):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=payload))
    ) as client:
        context = await service(client).context(LAT, LNG)
    assert context.source_statuses.weather.status == "error"
    assert context.source_statuses.fires.status == "error"


@pytest.mark.anyio
async def test_missing_google_credentials_firms_still_works():
    calls = []

    def handler(request):
        calls.append(request.url.host)
        return provider_response(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        environment = service(client, EnvironmentSettings(firms_key=TEST_KEY))
        context = await environment.context(LAT, LNG)
        config = environment.sources()
    assert context.source_statuses.air_quality.status == "not_configured"
    assert context.source_statuses.weather.status == "not_configured"
    assert context.source_statuses.fires.status == "live"
    assert len(calls) == 1 and not config.weather.configured and config.fires.configured
    assert TEST_KEY not in config.model_dump_json()


@pytest.mark.anyio
async def test_successful_empty_fires_is_not_unavailable():
    header = (FIXTURES / "firms.csv").read_text().splitlines()[0] + "\n"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=header))
    ) as client:
        env = service(client, EnvironmentSettings(firms_key=TEST_KEY))
        first, second = await env.context(LAT, LNG), await env.context(LAT, LNG)
    assert first.fires == [] and first.source_statuses.fires.status == "live"
    assert second.fires == [] and second.source_statuses.fires.status == "cached"


@pytest.mark.anyio
async def test_cache_expiry_exact_coordinates_and_copy_isolation():
    now, calls = [0.0], []

    def handler(request):
        calls.append(request)
        return provider_response(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        env = service(client, clock=lambda: now[0])
        first = await env.context(LAT, LNG)
        first.air_quality.indexes.clear()
        cached = await env.context(LAT, LNG)
        assert len(cached.air_quality.indexes) == 2
        assert cached.air_quality.status == "cached"
        assert cached.air_quality.retrieved_at == first.air_quality.retrieved_at
        assert len(calls) == 3
        now[0] = 601
        mixed = await env.context(LAT, LNG)
        assert mixed.source_statuses.air_quality.status == "live"
        assert mixed.source_statuses.fires.status == "cached"
        assert len(calls) == 5
        await env.context(LAT + 0.00001, LNG)
        assert len(calls) == 8


@pytest.mark.anyio
async def test_cache_is_bounded_and_coalesces_concurrent_queries():
    calls = []

    async def handler(request):
        calls.append(request)
        await asyncio.sleep(0.01)
        return provider_response(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        env = service(client)
        await asyncio.gather(env.context(LAT, LNG), env.context(LAT, LNG))
        assert len(calls) == 3
        env.settings.cache_max_entries = 3
        await env.context(LAT + 0.01, LNG)
        assert len(env.cache) == 3


@pytest.mark.anyio
async def test_direction_north_zero_and_missing_values():
    raw = {"currentTime": "2026-09-10T00:00:00Z", "wind": {"direction": {"degrees": 360}}}
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=raw))
    ) as client:
        observation = await GoogleWeatherProvider(ProviderHTTP(client, 8), TEST_KEY).fetch(LAT, LNG)
    assert observation.wind_from_degrees == 0 and observation.temperature is None


@pytest.mark.anyio
async def test_no_usable_google_data():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}))
    ) as client:
        context = await service(client).context(LAT, LNG)
    assert context.air_quality is None and context.weather is None
    assert context.source_statuses.air_quality.status == "unavailable"


def test_context_endpoint_missing_credentials_and_reference_time():
    with TestClient(create_app()) as client:
        response = client.get(
            "/api/v1/environment/context",
            params={"lat": LAT, "lng": LNG, "at": "2020-01-01T00:00:00Z"},
        )
        assert response.status_code == 200
        context = EnvironmentalContext.model_validate(response.json())
        assert all(s.status == "not_configured" for _, s in context.source_statuses)
        assert context.time_mode == "current" and context.requested_reference_time.year == 2020
        assert context.incident_relationship == "independent_context_not_demo_corroboration"
        assert all(not s.configured for _, s in context.source_statuses)
        assert (
            client.get("/api/v1/environment/sources").json()["weather"]["configuration_state"]
            == "not_configured"
        )


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"lat": 91, "lng": 0},
        {"lat": -91, "lng": 0},
        {"lat": 0, "lng": 181},
        {"lat": 0, "lng": -181},
        {"lat": "nan", "lng": 0},
        {"lat": 0, "lng": "inf"},
        {"lat": "bad", "lng": LNG},
        {"lat": LAT, "lng": LNG, "at": "2020-01-01T00:00:00"},
        {"lat": LAT, "lng": LNG, "at": "not-a-date"},
    ],
)
def test_invalid_context_request(params):
    with TestClient(create_app()) as client:
        assert client.get("/api/v1/environment/context", params=params).status_code == 422


@pytest.mark.anyio
async def test_no_secrets_in_structured_logs(caplog):
    logger.addHandler(caplog.handler)
    try:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(403, text=TEST_KEY))
        ) as client:
            await service(client).context(LAT, LNG)
        assert TEST_KEY not in caplog.text
        records = [
            json.loads(r.message) for r in caplog.records if r.name == "airshedos.environment"
        ]
        assert len(records) == 4
        assert sum(r["provider"] != "earth_engine_sentinel5p" for r in records) == 3
        assert all(
            set(r) == {"event", "provider", "success", "status", "latency_ms"} for r in records
        )
    finally:
        logger.removeHandler(caplog.handler)


@pytest.mark.anyio
async def test_oversized_provider_response_is_rejected():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 2_000_001))
    ) as client:
        with pytest.raises(ProviderFailure):
            await ProviderHTTP(client, 8).request("GET", "https://example.test")


def test_firms_invalid_key_message_is_not_zero_detections():
    provider = NasaFirmsProvider(None, TEST_KEY, 25)
    with pytest.raises(ValueError):
        provider.normalize("Invalid MAP_KEY", LAT, LNG, datetime.now(UTC))


@pytest.mark.anyio
async def test_cache_purges_without_another_request():
    async with httpx.AsyncClient(transport=httpx.MockTransport(provider_response)) as client:
        environment = service(
            client,
            EnvironmentSettings(
                google_key=TEST_KEY,
                firms_key=TEST_KEY,
                cache_ttl_seconds=1,
                firms_cache_ttl_seconds=1,
            ),
        )
        await environment.context(LAT, LNG)
        assert len(environment.cache) == 3
        await asyncio.sleep(1.05)
        assert not environment.cache and not environment.expiry_handles


@pytest.mark.anyio
async def test_provider_lock_wait_has_deadline_and_preserves_other_sources():
    async with httpx.AsyncClient(transport=httpx.MockTransport(provider_response)) as client:
        environment = service(
            client,
            EnvironmentSettings(
                google_key=TEST_KEY,
                firms_key=TEST_KEY,
                timeout_seconds=1,
            ),
        )
        async with environment.locks["weather"]:
            context = await environment.context(LAT, LNG)
        assert context.source_statuses.weather.status == "unavailable"
        assert "deadline" in context.source_statuses.weather.message
        assert context.air_quality and context.fires
        # Cancellation must not leave the provider lock permanently acquired.
        assert (await environment.context(LAT, LNG)).weather is not None


def test_configured_context_endpoint_with_mock_transport():
    client = httpx.AsyncClient(transport=httpx.MockTransport(provider_response))
    with TestClient(create_app(service(client))) as api:
        result = api.get(f"/api/v1/environment/context?lat={LAT}&lng={LNG}")
        assert result.status_code == 200
        body = EnvironmentalContext.model_validate(result.json())
        assert body.air_quality and body.weather and body.fires
        assert TEST_KEY not in result.text
    asyncio.run(client.aclose())


@pytest.mark.anyio
@pytest.mark.parametrize("dataset", ["VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT", "VIIRS_SNPP_NRT"])
async def test_firms_configured_dataset_in_request_and_provenance(dataset):
    requests = []

    def handler(request):
        requests.append(request)
        return provider_response(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        env = service(client, EnvironmentSettings(firms_key=TEST_KEY, firms_dataset=dataset))
        first = await env.context(LAT, LNG)
        second = await env.context(LAT, LNG)
    assert len(requests) == 1
    assert f"/{dataset}/" in requests[0].url.path
    assert first.fire_dataset == second.fire_dataset == dataset
    assert first.fires[0].source_id.startswith(dataset + ":")
    assert dataset in first.fires[0].provenance.method
    assert second.fires[0].provenance == first.fires[0].provenance
    assert second.source_statuses.fires.status == "cached"


def test_firms_dataset_configuration(monkeypatch):
    from pydantic import ValidationError

    monkeypatch.delenv("FIRMS_DATASET", raising=False)
    assert EnvironmentSettings.from_env().firms_dataset == "VIIRS_NOAA20_NRT"
    monkeypatch.setenv("FIRMS_DATASET", "VIIRS_NOAA21_NRT")
    assert EnvironmentSettings.from_env().firms_dataset == "VIIRS_NOAA21_NRT"
    monkeypatch.setenv("FIRMS_DATASET", "unsupported")
    with pytest.raises(ValidationError):
        EnvironmentSettings.from_env()
