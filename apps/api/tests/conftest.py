import httpx
import pytest


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    """CI must never make a live provider call, even if credentials exist on a runner."""
    monkeypatch.delenv("GOOGLE_MAPS_PLATFORM_API_KEY", raising=False)
    monkeypatch.delenv("NASA_FIRMS_MAP_KEY", raising=False)

    async def blocked(*args, **kwargs):
        raise AssertionError("Live networking is forbidden in unit tests")

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked)


@pytest.fixture
def anyio_backend():
    return "asyncio"
