"""Synthetic observations and SDK graph serialization only; never live Earth Engine."""

import asyncio
import json
import threading
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import ee
import google.auth
import httpx
import pytest
from ee.apitestcase import GetAlgorithms
from fastapi.testclient import TestClient
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from test_environment import LAT, LNG, provider_response, service

from app.environment.models import SatelliteSearchWindow
from app.environment.satellite import (
    PRODUCTS,
    EarthEngineClient,
    EarthEngineSentinel5PProvider,
    SatelliteQuery,
    normalize,
)
from app.environment.settings import EnvironmentSettings
from app.main import create_app

END = datetime(2026, 9, 11, 0, tzinfo=UTC)
QUERY = SatelliteQuery(
    LAT,
    LNG,
    SatelliteSearchWindow(
        start=END - timedelta(hours=72), end=END, lookback_hours=72, end_mode="explicit"
    ),
    10,
)
FIXTURE = json.loads((Path(__file__).parent / "fixtures/sentinel5p.json").read_text())


class FakeClient:
    def __init__(self, overrides=None):
        self.calls = []
        self.overrides = overrides or {}

    def query(self, product, query):
        self.calls.append((product, query))
        result = self.overrides.get(product, FIXTURE[product])
        if isinstance(result, Exception):
            raise result
        return deepcopy(result)


def provider(overrides=None):
    return EarthEngineSentinel5PProvider("test-project", client=FakeClient(overrides))


@pytest.mark.parametrize(
    "product,unit", [("no2", "mol/m²"), ("co", "mol/m²"), ("aerosol_index", "dimensionless")]
)
def test_normalization_units_times_quality_provenance(product, unit):
    result = normalize(product, FIXTURE[product], QUERY, END)
    obs = result.observation
    assert result.availability == "available" and result.status == "live"
    assert obs.unit == unit and obs.value == FIXTURE[product]["observation"]["value"]
    assert obs.observed_at == datetime(2026, 9, 10, 8, tzinfo=UTC)
    assert obs.retrieved_at == END and obs.age_seconds == 16 * 3600
    assert obs.image_id == obs.provenance.source_id
    assert obs.collection == PRODUCTS[product][0] and obs.band == PRODUCTS[product][1]
    assert obs.quality.status == "usable" and obs.quality.valid_grid_cells == 120
    assert "confidence" in obs.quality.note
    assert obs.source_product_id.startswith("SYNTHETIC")
    assert not obs.provenance.is_demo and obs.retrieval_radius_km == 10


@pytest.mark.parametrize(
    "counts,reason",
    [((0, 0), "no_scene"), ((3, 0), "quality_filtered"), ((3, 2), "no_usable_pixels")],
)
def test_absence_is_not_provider_failure(counts, reason):
    result = normalize(
        "no2",
        dict(scene_count=counts[0], quality_scene_count=counts[1], observation=None),
        QUERY,
        END,
    )
    assert result.status == "unavailable" and result.availability == reason
    assert result.observation is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("value", float("nan")),
        ("value", True),
        ("value", "0.2"),
        ("value", -0.002),
        ("observed_ms", END.timestamp() * 1000),
        ("observed_ms", (END - timedelta(days=8)).timestamp() * 1000),
        ("image_id", "wrong/asset"),
        ("product_quality", "Degraded"),
        ("processing_status", "Degraded"),
        ("valid_count", 0),
    ],
)
def test_malformed_or_unusable_observation_rejected(field, value):
    raw = deepcopy(FIXTURE["no2"])
    raw["observation"][field] = value
    with pytest.raises((ValueError, TypeError)):
        normalize("no2", raw, QUERY, END)


def test_negative_column_and_aerosol_values_retained():
    for product, value in [("no2", -0.00001), ("co", -0.0001), ("aerosol_index", -2.3)]:
        raw = deepcopy(FIXTURE[product])
        raw["observation"]["value"] = value
        assert normalize(product, raw, QUERY, END).observation.value == value


@pytest.mark.anyio
async def test_partial_products_and_malformed_provider_result():
    p = provider(
        {"co": {}, "aerosol_index": dict(scene_count=0, quality_scene_count=0, observation=None)}
    )
    result = await p.fetch(QUERY)
    assert [r.availability for r in result] == ["available", "provider_error", "no_scene"]
    assert len(p.client.calls) == 3


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exc,reason,status",
    [
        (DefaultCredentialsError("secret"), "not_configured", "not_configured"),
        (RefreshError("secret"), "authentication_error", "error"),
        (RuntimeError("403 secret"), "authentication_error", "error"),
        (RuntimeError("Project not registered secret"), "configuration_error", "error"),
        (RuntimeError("secret"), "provider_error", "error"),
        (TimeoutError("secret"), "timeout", "unavailable"),
    ],
)
async def test_failure_classification_no_secret_leak(exc, reason, status):
    p = provider({k: exc for k in PRODUCTS})
    result = await p.fetch(QUERY)
    assert all(r.availability == reason and r.status == status for r in result)
    assert "secret" not in "".join(r.model_dump_json() for r in result)
    if reason in ("not_configured", "authentication_error", "configuration_error"):
        assert len(p.client.calls) == 1


@pytest.mark.anyio
async def test_missing_project_never_initializes_sdk(monkeypatch):
    monkeypatch.setattr(google.auth, "default", lambda **_: pytest.fail("Unexpected ADC lookup"))
    result = await EarthEngineSentinel5PProvider("").fetch(QUERY)
    assert all(r.status == "not_configured" for r in result)


@pytest.mark.anyio
async def test_missing_adc_with_real_client(monkeypatch):
    def missing(**kwargs):
        raise DefaultCredentialsError("missing")

    monkeypatch.setattr(google.auth, "default", missing)
    result = await EarthEngineSentinel5PProvider("test-project").fetch(QUERY)
    assert all(r.availability == "not_configured" for r in result)


@pytest.mark.anyio
async def test_timeout_keeps_completed_product_and_does_not_queue():
    release = threading.Event()
    fake = FakeClient()
    original = fake.query

    def slow(product, query):
        if product == "co":
            release.wait(2)
        return original(product, query)

    fake.query = slow
    p = EarthEngineSentinel5PProvider("test-project", timeout_seconds=0.08, client=fake)
    try:
        result = await p.fetch(QUERY)
        assert [r.availability for r in result] == ["available", "timeout", "timeout"]
        assert all(r.availability == "busy" for r in await p.fetch(QUERY))
    finally:
        release.set()
        await p.active_task
    assert len(fake.calls) == 2  # Deadline prevents the third RPC.


@pytest.mark.parametrize("product", PRODUCTS)
def test_official_sdk_query_graph_filters_selects_latest_and_preserves_units(monkeypatch, product):
    # Official SDK's bundled offline algorithm definitions validate client-side API usage.
    ee.Reset()
    monkeypatch.setattr(ee.data, "_install_cloud_api_resource", lambda: None)
    monkeypatch.setattr(ee.data, "getAlgorithms", GetAlgorithms)
    ee.Initialize(None, "", project="test-project")
    captured = []

    def compute(obj):
        captured.append(json.loads(obj.serialize()))
        return FIXTURE[product]

    monkeypatch.setattr(ee.data, "computeValue", compute)
    client = EarthEngineClient("test-project")
    client.initialized = True
    try:
        assert client.query(product, QUERY) == FIXTURE[product]
        graph = json.dumps(captured[0])
        for required in (
            PRODUCTS[product][0],
            PRODUCTS[product][1],
            "PRODUCT_QUALITY",
            "PROCESSING_STATUS",
            "Nominal",
            "Geometry.buffer",
            "Number.max",
            "Image.reduceRegion",
            "Reducer.mean",
            "Reducer.count",
            "Collection.limit",
            "observed_ms",
            "system:time_start",
            "system:index",
            "Filter.notNull",
            "If",
            "1113.2",
            "10000",
        ):
            assert required in graph

        # Most-recent usable, not simply first/newest image: filter before descending sort.
        def nodes(obj):
            if isinstance(obj, dict):
                yield obj
                for value in obj.values():
                    yield from nodes(value)
            elif isinstance(obj, list):
                for value in obj:
                    yield from nodes(value)

        sort = next(
            v["functionInvocationValue"]
            for v in nodes(captured[0])
            if v.get("functionInvocationValue", {}).get("functionName") == "Collection.limit"
        )
        assert sort["arguments"]["key"] == {"constantValue": "observed_ms"}
        assert sort["arguments"]["ascending"] == {"constantValue": False}
        assert ("Image.gte" in graph) == (product != "aerosol_index")
        assert "qa_value" not in graph and "multiply" not in graph
    finally:
        ee.Reset()


@pytest.mark.anyio
async def test_satellite_cache_keys_expiry_copy_and_shared_endpoint():
    clock = [0]
    async with httpx.AsyncClient(transport=httpx.MockTransport(provider_response)) as client:
        env = service(client, clock=lambda: clock[0])
        env.satellite = provider()
        first = await env.satellite_context(LAT, LNG, END)
        first.products[0].observation.value = 99
        cached = await env.satellite_context(LAT + 0.000001, LNG, END)
        assert cached.provider_status.status == "cached" and all(
            p.cache_hit for p in cached.products
        )
        assert cached.products[0].observation.value != 99
        assert (
            cached.products[0].observation.retrieved_at
            == first.products[0].observation.retrieved_at
        )
        assert cached.latitude != cached.query_latitude
        assert len(env.satellite.client.calls) == 3
        context = await env.context(LAT, LNG, END)
        assert context.satellite.provider_status.status == "cached"
        assert context.air_quality and context.weather and context.fires
        assert len(env.satellite.client.calls) == 3
        await env.satellite_context(LAT, LNG, END, lookback_hours=48)
        await env.satellite_context(LAT + 0.001, LNG, END)
        await env.satellite_context(LAT, LNG, END + timedelta(hours=1))
        assert len(env.satellite.client.calls) == 12
        clock[0] = 3601
        assert (await env.satellite_context(LAT, LNG, END)).provider_status.status == "live"
        assert len(env.satellite.client.calls) == 15


@pytest.mark.anyio
async def test_empty_search_cached_errors_not_cached_and_partial_availability():
    async with httpx.AsyncClient(transport=httpx.MockTransport(provider_response)) as client:
        env = service(client)
        env.satellite = provider(
            {k: dict(scene_count=0, quality_scene_count=0, observation=None) for k in PRODUCTS}
        )
        first = await env.satellite_context(LAT, LNG, END)
        cached = await env.satellite_context(LAT, LNG, END)
        assert first.availability == "none" and first.provider_status.status == "live"
        assert cached.provider_status.status == "cached"
        assert all(p.availability == "no_scene" and p.cache_hit for p in cached.products)
        env.satellite = provider({"co": RuntimeError("bad")})
        partial = await env.satellite_context(LAT + 0.01, LNG, END)
        assert partial.availability == "partial" and partial.provider_status.status == "live"
        await env.satellite_context(LAT + 0.01, LNG, END)
        assert len(env.satellite.client.calls) == 6


@pytest.mark.anyio
async def test_ground_request_independent_while_satellite_waits_and_concurrent_coalescing():
    async with httpx.AsyncClient(transport=httpx.MockTransport(provider_response)) as client:
        env = service(client)
        env.satellite = provider()
        async with env.satellite_lock:
            context = await asyncio.wait_for(env.context(LAT, LNG, include_satellite=False), 1)
        assert (
            context.satellite is None and context.air_quality and context.weather and context.fires
        )
        assert not env.satellite.client.calls
        await asyncio.gather(
            env.satellite_context(LAT, LNG, END), env.satellite_context(LAT, LNG, END)
        )
        assert len(env.satellite.client.calls) == 3


def test_satellite_routes_config_time_window_and_ground_compatibility():
    with TestClient(create_app()) as client:
        url = "/api/v1/environment/satellite"
        response = client.get(url, params={"lat": LAT, "lng": LNG})
        body = response.json()
        assert response.status_code == 200 and body["provider_status"]["status"] == "not_configured"
        assert body["search_window"]["lookback_hours"] == 72
        assert datetime.fromisoformat(body["search_window"]["end"]).minute == 0
        for extra in (
            {"lookback_hours": 0},
            {"lookback_hours": 169},
            {"at": "bad"},
            {"at": "2026-01-01T00:00:00"},
            {"lat": "nan"},
            {"lng": 181},
        ):
            assert client.get(url, params={"lat": LAT, "lng": LNG, **extra}).status_code == 422
        full = client.get("/api/v1/environment/context", params={"lat": LAT, "lng": LNG}).json()
        assert full["satellite"]["availability"] == "none"
        assert set(full["source_statuses"]) == {"air_quality", "weather", "fires"}


def test_project_fallback_configuration(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "shared-project")
    assert EnvironmentSettings.from_env().earth_engine_project == "shared-project"
    monkeypatch.setenv("EARTH_ENGINE_PROJECT", "satellite-project")
    assert EnvironmentSettings.from_env().earth_engine_project == "satellite-project"


@pytest.mark.anyio
async def test_live_cli_satellite_mode_with_fake_queries(monkeypatch, capsys):
    from scripts import verify_environment_sources as script

    monkeypatch.setattr(script, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(
        script.sys,
        "argv",
        [
            "verify",
            "--lat",
            str(LAT),
            "--lng",
            str(LNG),
            "--satellite-only",
            "--gate",
            "--at",
            END.isoformat(),
        ],
    )
    real_service = script.EnvironmentService
    fake = provider()

    def factory(*args):
        return real_service(*args, satellite=fake)

    monkeypatch.setattr(script, "EnvironmentService", factory)
    await script.main()
    output = json.loads(capsys.readouterr().out)
    assert output["satellite_verification"]["gate_pass"]
    assert output["satellite_verification"]["product_queries_after_first"] == 3
    assert output["satellite_verification"]["product_queries_after_cache"] == 3


@pytest.mark.anyio
async def test_live_cli_missing_config_is_failed_gate_not_missing_coverage(monkeypatch, capsys):
    from scripts import verify_environment_sources as script

    monkeypatch.setattr(script, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(
        script.sys,
        "argv",
        ["verify", "--lat", str(LAT), "--lng", str(LNG), "--satellite-only", "--gate"],
    )
    with pytest.raises(SystemExit) as exc:
        await script.main()
    assert exc.value.code == 2
    output = json.loads(capsys.readouterr().out)
    assert not output["satellite_verification"]["gate_pass"]
    assert all(p["availability"] == "not_configured" for p in output["satellite"]["products"])
