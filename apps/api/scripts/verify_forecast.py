"""Manual Gurugram integration gate; no accuracy claim. Never invoked by CI."""

import asyncio
import json
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.environment.forecast import GoogleAirQualityForecastProvider  # noqa: E402
from app.environment.http import ProviderHTTP  # noqa: E402
from app.environment.providers import (  # noqa: E402
    GoogleAirQualityProvider,
    GoogleWeatherProvider,
    NasaFirmsProvider,
)
from app.environment.service import EnvironmentService  # noqa: E402
from app.environment.settings import EnvironmentSettings  # noqa: E402


async def main():
    load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)
    settings = EnvironmentSettings.from_env()
    counts = {"forecast": 0, "current": 0}

    async def record(response):
        path = response.request.url.path
        if path.endswith("forecast:lookup"):
            counts["forecast"] += 1
        elif path.endswith("currentConditions:lookup"):
            counts["current"] += 1

    async with httpx.AsyncClient(
        follow_redirects=False, event_hooks={"response": [record]}
    ) as client:
        http = ProviderHTTP(client, settings.timeout_seconds)
        key = settings.google_key.get_secret_value()
        env = EnvironmentService(
            GoogleAirQualityProvider(http, key),
            GoogleWeatherProvider(http, key),
            NasaFirmsProvider(
                http,
                settings.firms_key.get_secret_value(),
                settings.firms_radius_km,
                settings.firms_dataset,
            ),
            settings,
            forecast=GoogleAirQualityForecastProvider(http, key),
        )
        first = await env.forecast_context(28.4595, 77.0266)
        counts_first = counts.copy()
        cached = await env.forecast_context(28.4595, 77.0266, 6)
        gate = {
            "live_pass": first.provider_status.status == "live",
            "current_pass": first.current_source_status.status == "live",
            "horizons_pass": len(first.summaries) == 3
            and all(
                s.coverage == "complete" and s.pm25_hours == s.horizon_hours
                for s in first.summaries
            ),
            "cache_pass": cached.provider_status.status == "cached"
            and counts == counts_first
            and first.retrieved_at == cached.retrieved_at
            and first.hourly_forecasts[:6] == cached.hourly_forecasts,
            "requests_after_live": counts_first,
            "requests_after_cache": counts,
            "cached_latency_ms": cached.provider_status.latency_ms,
            "cpcb_available": [s.cpcb_hours for s in first.summaries],
            "claim": (
                "Integration verification only; no forecast accuracy "
                "or historical evaluation claim."
            ),
        }
        gate["pass"] = all(
            gate[k] for k in ("live_pass", "current_pass", "horizons_pass", "cache_pass")
        )
        print(
            json.dumps({"verification": gate, "forecast": first.model_dump(mode="json")}, indent=2)
        )
        return 0 if gate["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
