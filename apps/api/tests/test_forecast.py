"""Synthetic Google-shaped fixtures only; never a live request or accuracy evaluation."""

import asyncio
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from test_corroboration import context, report
from test_environment import TEST_KEY, provider_response, service

from app.environment.forecast import GoogleAirQualityForecastProvider, classify, summarize
from app.environment.http import ProviderHTTP
from app.environment.settings import EnvironmentSettings
from app.main import create_app

ANCHOR = datetime(2026, 9, 16, tzinfo=UTC)
LAT, LNG = 28.4595, 77.0266
FIXTURE = Path(__file__).parent / "fixtures/google_forecast.json"


def payload(anchor=ANCHOR):
    raw = json.loads(FIXTURE.read_text())
    for h, row in enumerate(raw["hourlyForecasts"], 1):
        row["dateTime"] = (anchor + timedelta(hours=h)).isoformat()
    return raw


async def normalized(raw=None):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=raw or payload()))
    ) as client:
        return await GoogleAirQualityForecastProvider(ProviderHTTP(client, 1), TEST_KEY).fetch(
            LAT, LNG, ANCHOR + timedelta(hours=1), ANCHOR + timedelta(hours=24)
        )


def current():
    aq = context().air_quality
    aq.observed_at = ANCHOR
    aq.pollutants[0].concentration.value = 30
    return aq


@pytest.mark.anyio
async def test_normalization_native_units_cpcb_timestamps_and_request():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=payload())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await GoogleAirQualityForecastProvider(ProviderHTTP(client, 1), TEST_KEY).fetch(
            LAT, LNG, ANCHOR + timedelta(hours=1), ANCHOR + timedelta(hours=24)
        )
    rows = result["hourly_forecasts"]
    assert len(rows) == 24 and result["region_code"] == "in"
    assert rows[0].forecast_at == ANCHOR + timedelta(hours=1)
    assert rows[-1].forecast_at == ANCHOR + timedelta(hours=24)
    assert rows[0].indexes[1].code == "ind_cpcb" and rows[0].indexes[1].value == 105
    assert rows[0].dominant_pollutant == "pm25"
    assert rows[0].pollutants[0].concentration.value == 32
    assert rows[0].pollutants[0].concentration.unit == "MICROGRAMS_PER_CUBIC_METER"
    assert rows[0].pollutants[2].concentration.unit == "PARTS_PER_BILLION"
    assert result["retrieved_at"].utcoffset() == timedelta(0)
    body = json.loads(requests[0].content)
    assert body["pageSize"] == 24 and "dateTime" not in body
    assert body["period"]["endTime"] == rows[-1].forecast_at.isoformat()
    assert set(body["extraComputations"]) == {"LOCAL_AQI", "POLLUTANT_CONCENTRATION"}
    assert requests[0].headers["X-Goog-Api-Key"] == TEST_KEY
    assert TEST_KEY not in str(requests[0].url)


@pytest.mark.anyio
@pytest.mark.parametrize("horizon,pm,aqi", [(6, 42, 130), (12, 54, 160), (24, 78, 220)])
async def test_horizon_summary(horizon, pm, aqi):
    rows = (await normalized())["hourly_forecasts"]
    result = summarize(rows, ANCHOR, horizon, current(), ANCHOR)
    assert result.max_pm25.value == pm and result.max_cpcb_aqi == aqi
    assert result.max_pm10.value == 60 + horizon * 3
    assert result.peak_at == ANCHOR + timedelta(hours=horizon)
    assert result.cpcb_peak_at == result.pm10_peak_at == result.peak_at
    assert result.delta_pm25_vs_current.value == pm - 30
    assert result.relative_pm25_change_percent == pytest.approx((pm - 30) / 30 * 100)
    assert result.coverage == "complete" and result.available_hours == horizon
    assert result.worst_category == ("Poor" if horizon == 24 else "Moderate")
    assert result.outlook == ("SHARPLY_WORSENING" if horizon == 24 else "WORSENING")


@pytest.mark.parametrize(
    "base,peak,expected",
    [
        (30, 34.99, "STABLE"),
        (30, 35, "WORSENING"),
        (30, 55, "SHARPLY_WORSENING"),
        (30, 25, "IMPROVING"),
        (100, 109, "STABLE"),
        (100, 110, "WORSENING"),
        (100, 149, "WORSENING"),
        (100, 150, "SHARPLY_WORSENING"),
        (100, 90, "IMPROVING"),
        (0, 0, "STABLE"),
        (0, 5, "WORSENING"),
    ],
)
def test_transparent_threshold_boundaries(base, peak, expected):
    assert classify(base, peak) == expected


@pytest.mark.anyio
async def test_missing_cpcb_never_substitutes_uaqi_and_earliest_peak_tie():
    raw = payload()
    for row in raw["hourlyForecasts"]:
        row["indexes"] = row["indexes"][:1]
        row["pollutants"][0]["concentration"]["value"] = 40
    rows = (await normalized(raw))["hourly_forecasts"]
    result = summarize(rows, ANCHOR, 6, current(), ANCHOR)
    assert result.max_cpcb_aqi is result.worst_category is result.cpcb_peak_at is None
    assert result.cpcb_hours == 0 and result.max_pm25.value == 40
    assert result.peak_at == ANCHOR + timedelta(hours=1)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "case",
    [
        "missing_current",
        "stale",
        "future",
        "different_units",
        "partial",
        "mixed_forecast_units",
        "unsupported_unit",
    ],
)
async def test_comparison_withheld_when_not_meaningful(case):
    rows = (await normalized())["hourly_forecasts"]
    aq = current()
    if case == "missing_current":
        aq = None
    elif case == "stale":
        aq.observed_at -= timedelta(hours=3)
    elif case == "future":
        aq.observed_at += timedelta(minutes=6)
    elif case == "different_units":
        aq.pollutants[0].concentration.unit = "PARTS_PER_BILLION"
    elif case == "partial":
        rows.pop(0)
    elif case == "mixed_forecast_units":
        rows[0].pollutants[0].concentration.unit = "PARTS_PER_BILLION"
    elif case == "unsupported_unit":
        aq.pollutants[0].concentration.unit = "PARTS_PER_BILLION"
        for row in rows:
            row.pollutants[0].concentration.unit = "PARTS_PER_BILLION"
    result = summarize(rows, ANCHOR, 6, aq, ANCHOR)
    assert result.outlook == "UNAVAILABLE"
    if case not in ("partial", "unsupported_unit"):
        assert result.delta_pm25_vs_current is None


@pytest.mark.anyio
async def test_zero_current_has_no_infinite_percentage():
    aq = current()
    aq.pollutants[0].concentration.value = 0
    result = summarize((await normalized())["hourly_forecasts"], ANCHOR, 6, aq, ANCHOR)
    assert result.relative_pm25_change_percent is None and result.delta_pm25_vs_current.value == 42


@pytest.mark.anyio
@pytest.mark.parametrize(
    "case",
    [
        "naive",
        "out_of_window",
        "duplicate_hour",
        "duplicate_product",
        "negative",
        "nan",
        "bad_shape",
    ],
)
async def test_malformed_provider_data_rejected(case):
    raw = payload()
    row = raw["hourlyForecasts"][0]
    if case == "naive":
        row["dateTime"] = "2026-09-16T01:00:00"
    elif case == "out_of_window":
        row["dateTime"] = ANCHOR.isoformat()
    elif case == "duplicate_hour":
        raw["hourlyForecasts"].append(deepcopy(row))
    elif case == "duplicate_product":
        row["indexes"].append(deepcopy(row["indexes"][0]))
    elif case in ("negative", "nan"):
        row["pollutants"][0]["concentration"]["value"] = -1 if case == "negative" else "NaN"
    else:
        raw["hourlyForecasts"] = "bad"
    with pytest.raises((ValueError, TypeError)):
        await normalized(raw)


@pytest.mark.anyio
async def test_pagination_and_cycle_guard():
    calls = []
    raw = payload()

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(
            200,
            json={
                "regionCode": "in",
                "hourlyForecasts": raw["hourlyForecasts"][12:]
                if "pageToken" in body
                else raw["hourlyForecasts"][:12],
                **({} if "pageToken" in body else {"nextPageToken": "synthetic-page-2"}),
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GoogleAirQualityForecastProvider(ProviderHTTP(client, 1), TEST_KEY)
        result = await provider.fetch(
            LAT, LNG, ANCHOR + timedelta(hours=1), ANCHOR + timedelta(hours=24)
        )
    assert len(result["hourly_forecasts"]) == 24 and len(calls) == 2
    assert calls[1]["pageToken"] == "synthetic-page-2"
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"nextPageToken": "cycle"})
        )
    ) as client:
        with pytest.raises(ValueError, match="pagination"):
            await GoogleAirQualityForecastProvider(ProviderHTTP(client, 1), TEST_KEY).fetch(
                LAT, LNG, ANCHOR, ANCHOR
            )


def forecast_service(client, **kwargs):
    env = service(client, **kwargs)
    env.forecast = GoogleAirQualityForecastProvider(ProviderHTTP(client, 1), TEST_KEY)
    return env


def live_shaped(request):
    if request.url.path.endswith("forecast:lookup"):
        return httpx.Response(
            200, json=payload(datetime.now(UTC).replace(minute=0, second=0, microsecond=0))
        )
    return provider_response(request)


@pytest.mark.anyio
async def test_cache_horizon_reuse_coordinate_expiry_copy_and_provenance():
    calls, clock = [], [0]

    def handler(request):
        calls.append(request.url.path)
        return live_shaped(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        env = forecast_service(client, clock=lambda: clock[0])
        first = await env.forecast_context(LAT, LNG, 6)
        second = await env.forecast_context(LAT, LNG, 24)
        assert first.provider_status.status == "live" and second.provider_status.status == "cached"
        assert len(first.hourly_forecasts) == 6 and len(second.hourly_forecasts) == 24
        assert first.retrieved_at == second.retrieved_at and second.issued_at is None
        assert first.provenance == second.provenance and not first.provenance.is_demo
        assert (
            first.provider == "google_air_quality_forecast"
            and TEST_KEY not in first.model_dump_json()
        )
        assert len(calls) == 2  # One forecast batch + one current AQ request.
        second.hourly_forecasts[0].pollutants[0].concentration.value = 999
        assert (await env.forecast_context(LAT, LNG)).hourly_forecasts[0].pollutants[
            0
        ].concentration.value == 32
        await env.forecast_context(LAT + 0.001, LNG)
        assert len(calls) == 4
        clock[0] = 901
        await env.forecast_context(LAT, LNG)
        assert len(calls) == 6


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure,state",
    [
        (403, "error"),
        (503, "unavailable"),
        ("timeout", "unavailable"),
        ("malformed", "error"),
        ("empty", "unavailable"),
        ("unconfigured", "not_configured"),
    ],
)
async def test_forecast_failure_preserves_current_and_other_sources(failure, state):
    def handler(request):
        if not request.url.path.endswith("forecast:lookup"):
            return provider_response(request)
        if failure == "timeout":
            raise httpx.ReadTimeout(TEST_KEY)
        if failure == "malformed":
            return httpx.Response(200, json={"hourlyForecasts": ["bad"]})
        if failure == "empty":
            return httpx.Response(200, json={})
        return httpx.Response(failure, text=TEST_KEY)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        env = forecast_service(client)
        if failure == "unconfigured":
            env.forecast = GoogleAirQualityForecastProvider(None, "")
        result = await env.forecast_context(LAT, LNG)
        existing = await env.context(LAT, LNG, include_satellite=False)
    assert result.provider_status.status == state and not result.hourly_forecasts
    assert result.current_air_quality and result.current_source_status.status == "live"
    assert existing.air_quality and existing.weather and existing.fires
    assert all(s.status in ("live", "cached") for _, s in existing.source_statuses)
    assert all(s.coverage == "none" and s.outlook == "UNAVAILABLE" for s in result.summaries)
    assert TEST_KEY not in result.model_dump_json()


@pytest.mark.anyio
async def test_forecast_lock_timeout_is_bounded_and_does_not_fetch_in_current_context():
    async with httpx.AsyncClient(transport=httpx.MockTransport(live_shaped)) as client:
        env = forecast_service(
            client, settings=EnvironmentSettings(google_key=TEST_KEY, timeout_seconds=1)
        )
        async with env.forecast_lock:
            result = await env.forecast_context(LAT, LNG)
            ground = await env.context(LAT, LNG, include_satellite=False)
        assert (
            result.provider_status.status == "unavailable"
            and "deadline" in result.provider_status.message
        )
        assert ground.air_quality and ground.weather
        assert (await env.forecast_context(LAT, LNG)).provider_status.status == "live"


@pytest.mark.parametrize("horizon", [6, 12, 24, 7, 96, "bad"])
def test_endpoint_horizons_and_configuration(horizon):
    with TestClient(create_app()) as client:
        response = client.get(
            "/api/v1/environment/forecast",
            params={"lat": LAT, "lng": LNG, "horizon_hours": horizon},
        )
    assert response.status_code == (200 if horizon in (6, 12, 24) else 422)
    if response.status_code == 200:
        assert response.json()["provider_status"]["status"] == "not_configured"
        assert len(response.json()["summaries"]) == {6: 1, 12: 2, 24: 3}[horizon]


def test_forecast_changes_never_change_corroboration_support_or_votes():
    from app.corroboration.engine import assess
    from app.corroboration.settings import CorroborationSettings

    record, ground = report(), context()

    class Environment:
        mode = "live"

        async def context(self, *args, **kwargs):
            return ground

        async def forecast_context(self, lat, lng, current_result):
            async with httpx.AsyncClient(transport=httpx.MockTransport(live_shaped)) as client:
                env = forecast_service(client)
                if self.mode == "unavailable":
                    env.forecast = GoogleAirQualityForecastProvider(None, "")
                result = await env.forecast_context(lat, lng, current_result=current_result)
                if self.mode == "extreme":
                    for summary in result.summaries:
                        summary.max_pm25.value = 900
                        summary.outlook = "SHARPLY_WORSENING"
                return result

    environment = Environment()
    with TestClient(create_app(environment=environment)) as client:
        # Insert on the application event loop, as the real analysis route does.
        async def insert():
            client.app.state.structured_reports.put(record)

        client.portal.call(insert)
        expected = assess(record, ground, CorroborationSettings()).model_dump(
            mode="json", exclude={"forecast_outlook"}
        )
        for mode in ("live", "extreme", "unavailable"):
            environment.mode = mode
            response = client.post(f"/api/v1/citizen-reports/{record.report.id}/corroborate")
            assert response.status_code == 200
            actual = response.json()
            outlook = actual.pop("forecast_outlook")
            assert (
                actual == expected
            )  # Every rule, reference, source, support and advisory identical.
            assert outlook["provider_status"]["status"] == (
                "not_configured" if mode == "unavailable" else "live"
            )


@pytest.mark.anyio
async def test_current_failure_does_not_hide_forecast_and_concurrent_requests_coalesce():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("currentConditions:lookup"):
            return httpx.Response(403)
        return live_shaped(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        env = forecast_service(client)
        first, second = await asyncio.gather(
            env.forecast_context(LAT, LNG), env.forecast_context(LAT, LNG)
        )
    assert {first.provider_status.status, second.provider_status.status} == {"live", "cached"}
    assert sum(path.endswith("forecast:lookup") for path in calls) == 1
    for result in (first, second):
        assert result.current_air_quality is None
        assert result.current_source_status.status == "error"
        assert len(result.hourly_forecasts) == 24
        assert all(s.outlook == "UNAVAILABLE" and s.max_pm25 for s in result.summaries)
