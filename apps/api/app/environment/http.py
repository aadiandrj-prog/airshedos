"""Bounded, secret-safe HTTP access. Only provider/status/latency are logged elsewhere."""

import asyncio
import logging

import httpx

from app.environment.models import SourceState


class ProviderFailure(Exception):
    def __init__(self, status: SourceState, message: str):
        self.status = status
        self.message = message
        super().__init__(message)


class ProviderHTTP:
    def __init__(self, client: httpx.AsyncClient, timeout_seconds: float):
        self.client = client
        self.timeout_seconds = timeout_seconds
        # httpx INFO logs include URLs; FIRMS credentials occur in the URL path.
        for name in ("httpx", "httpcore"):
            logging.getLogger(name).setLevel(logging.WARNING)

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async def bounded_read():
            async with self.client.stream(
                method, url, timeout=httpx.Timeout(self.timeout_seconds, connect=3), **kwargs
            ) as response:
                content = bytearray()
                async for part in response.aiter_bytes():
                    content.extend(part)
                    if len(content) > 2_000_000:
                        raise ProviderFailure(
                            SourceState.ERROR, "Provider response exceeded size limit."
                        )
                return httpx.Response(response.status_code, content=bytes(content))

        for attempt in range(2):
            try:
                response = await asyncio.wait_for(bounded_read(), timeout=self.timeout_seconds)
            except (httpx.TransportError, TimeoutError):
                if attempt == 0:
                    await asyncio.sleep(0.2)
                    continue
                raise ProviderFailure(
                    SourceState.UNAVAILABLE, "Provider timed out or could not be reached."
                ) from None
            if response.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                await asyncio.sleep(0.2)
                continue
            if response.status_code in (429, 500, 502, 503, 504):
                raise ProviderFailure(
                    SourceState.UNAVAILABLE, "Provider is temporarily unavailable or rate limited."
                )
            if response.status_code in (401, 403):
                raise ProviderFailure(
                    SourceState.ERROR,
                    "Provider rejected credentials or API access. Check backend configuration.",
                )
            if not 200 <= response.status_code < 300:
                raise ProviderFailure(SourceState.ERROR, "Provider rejected the request.")
            return response
        raise AssertionError("Retry bound exceeded")
