"""Synthetic providers + actual PostgreSQL quota; never live credentials or cases in responses."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from test_access import access_fixture as access_fixture
from test_access import fixture as fixture
from test_access import persistence_fixture as persistence_fixture
from test_access import pg as pg
from test_access import signing_key as signing_key
from test_environment import provider_response, service
from test_forecast import payload

from app.environment.forecast import GoogleAirQualityForecastProvider
from app.explore.service import OverviewService
from app.main import create_app


@pytest.fixture
def public(access_fixture, monkeypatch):
    monkeypatch.setenv("PUBLIC_OVERVIEW_ENABLED", "1")
    f = access_fixture
    calls = []
    failure = [None]

    def handler(request):
        calls.append(request)
        source = (
            "forecast"
            if "forecast:lookup" in request.url.path
            else "air_quality"
            if request.url.host == "airquality.googleapis.com"
            else "weather"
            if request.url.host == "weather.googleapis.com"
            else "fires"
        )
        if source == failure[0]:
            return httpx.Response(403)
        if source == "forecast":
            return httpx.Response(
                200, json=payload(datetime.now(UTC).replace(minute=0, second=0, microsecond=0))
            )
        return provider_response(request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    env = service(http)
    env.forecast = GoogleAirQualityForecastProvider(
        env.providers["air_quality"].http, "synthetic-test-key"
    )
    app = create_app(environment=env, access=f["service"], mode="pilot")
    with TestClient(app) as client:
        yield f | {"public": client, "environment": env, "calls": calls, "failure": failure}
    asyncio.run(http.aclose())


def test_public_projection_cached_without_case_or_identity(public):
    f = public
    response = f["public"].post("/api/v2/explore/areas/gurugram/overview", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["area"]["id"] == "gurugram"
    assert data["context"]["satellite"] is None
    assert data["context"]["air_quality"]["indexes"][0]["code"] == "uaqi"
    assert len(data["forecast"]["summaries"]) == 3
    assert data["forecast"]["summaries"][2]["horizon_hours"] == 24
    assert len(f["calls"]) == 4
    for private in (
        "Private reviewer note",
        "reporter_user_id",
        "binding_hash",
        "sealed_data",
        "synthetic-test-key",
    ):
        assert private not in response.text
    assert response.headers["cache-control"] == "private, no-store"
    again = f["public"].post("/api/v2/explore/areas/gurugram/overview", json={})
    assert again.status_code == 200 and len(f["calls"]) == 4
    assert again.json()["expires_at"] == data["expires_at"]
    assert again.json()["context"]["source_statuses"]["air_quality"]["status"] == "cached"
    assert (
        again.json()["context"]["air_quality"]["retrieved_at"]
        == data["context"]["air_quality"]["retrieved_at"]
    )
    import os

    if os.getenv("SEVA_CAPTURE_OVERVIEW") == "1":
        Path("/private/tmp/airshedos-overview-synthetic.json").write_text(
            json.dumps(data, indent=2)
        )


@pytest.mark.parametrize("source", ["air_quality", "weather", "fires", "forecast"])
def test_each_source_fails_independently(public, source):
    f = public
    f["failure"][0] = source
    r = f["public"].post("/api/v2/explore/areas/delhi/overview", json={})
    assert r.status_code == 200
    data = r.json()
    statuses = {k: v["status"] for k, v in data["context"]["source_statuses"].items()}
    statuses["forecast"] = data["forecast"]["provider_status"]["status"]
    assert statuses[source] == "error"
    assert all(v == "live" for k, v in statuses.items() if k != source)


def test_unknown_area_query_and_spoof_fields_make_no_calls(public):
    client = public["public"]
    assert client.get("/api/v2/explore/areas").status_code == 200
    assert client.post("/api/v2/explore/areas/world/overview", json={}).status_code == 404
    assert client.post("/api/v2/explore/areas/delhi/overview?lat=1", json={}).status_code == 422
    for field in ("latitude", "longitude", "user_id", "unit_id", "report_id", "role"):
        assert (
            client.post("/api/v2/explore/areas/delhi/overview", json={field: "spoof"}).status_code
            == 422
        )
    assert public["calls"] == []


def test_disabled_and_request_limit_stop_before_sources(public, monkeypatch):
    monkeypatch.setenv("PUBLIC_OVERVIEW_ENABLED", "0")
    assert public["public"].post("/api/v2/explore/areas/delhi/overview", json={}).status_code == 503
    monkeypatch.setenv("PUBLIC_OVERVIEW_ENABLED", "1")
    monkeypatch.setenv("PUBLIC_OVERVIEW_REQUESTS_PER_HOUR", "0")
    assert public["public"].post("/api/v2/explore/areas/delhi/overview", json={}).status_code == 429
    assert public["calls"] == []


def test_paid_quota_denied_before_any_google_invocation(public):
    f = public
    f["repo"].limits = f["repo"].limits.model_copy(update={"provider_calls_per_day": 0})
    r = f["public"].post(
        "/api/v2/explore/areas/delhi/overview", json={}, headers={"X-Forwarded-For": "1.2.3.4"}
    )
    assert r.status_code == 200
    assert all(request.url.host == "firms.modaps.eosdis.nasa.gov" for request in f["calls"])
    assert len(f["calls"]) == 1
    assert "budget reached" in r.text


@pytest.mark.anyio
async def test_two_service_instances_share_atomic_http_budget(public):
    f = public
    one = OverviewService(f["environment"], f["repo"], daily_limit=1)
    two = OverviewService(f["environment"], f["repo"], daily_limit=1)
    await asyncio.gather(one.overview("delhi"), two.overview("noida"))
    assert len(f["calls"]) == 1


def test_daily_denial_never_invokes_provider(public, monkeypatch):
    monkeypatch.setenv("PUBLIC_OVERVIEW_HTTP_PER_DAY", "0")
    r = public["public"].post("/api/v2/explore/areas/delhi/overview", json={})
    assert r.status_code == 200 and public["calls"] == []
    assert "budget reached" in r.text


def test_oversized_chunked_public_body_is_rejected_before_providers(public):
    r = public["public"].post(
        "/api/v2/explore/areas/delhi/overview",
        content=iter([b"{" + b" " * 100, b" " * 100 + b"}"]),
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 413 and public["calls"] == []


@pytest.mark.anyio
async def test_retry_attempts_are_metered_before_http(public):
    from app.environment.http import ProviderHTTP

    f = public
    calls = []

    def fail(_request):
        calls.append(1)
        return httpx.Response(503)

    client = httpx.AsyncClient(transport=httpx.MockTransport(fail))
    service = OverviewService(f["environment"], f["repo"], daily_limit=1)
    from app.environment.http import ProviderFailure, request_admission

    token = request_admission.set(service.admit_network)
    try:
        with pytest.raises(ProviderFailure, match="budget reached"):
            await ProviderHTTP(client, 1).request("GET", "https://weather.googleapis.com/v1/test")
    finally:
        request_admission.reset(token)
        await client.aclose()
    assert calls == [1]
