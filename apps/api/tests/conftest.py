import ee
import httplib2
import httpx
import pytest
import requests


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    """CI must never make a live provider call, even if credentials exist on a runner."""
    monkeypatch.delenv("GOOGLE_MAPS_PLATFORM_API_KEY", raising=False)
    monkeypatch.delenv("NASA_FIRMS_MAP_KEY", raising=False)

    for name in ("EARTH_ENGINE_PROJECT", "GOOGLE_CLOUD_PROJECT", "GOOGLE_APPLICATION_CREDENTIALS"):
        monkeypatch.delenv(name, raising=False)

    def blocked_sync(*args, **kwargs):
        raise AssertionError("Live Earth Engine networking is forbidden in unit tests")

    monkeypatch.setattr(ee.data, "computeValue", blocked_sync)
    monkeypatch.setattr(httplib2.Http, "request", blocked_sync)
    monkeypatch.setattr(requests.Session, "request", blocked_sync)

    async def blocked(*args, **kwargs):
        raise AssertionError("Live networking is forbidden in unit tests")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)


@pytest.fixture
def anyio_backend():
    return "asyncio"
