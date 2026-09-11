"""Manual only. Never called by CI. Reads optional root .env without printing secrets."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.environment.http import ProviderHTTP  # noqa: E402
from app.environment.providers import (  # noqa: E402
    GoogleAirQualityProvider,
    GoogleWeatherProvider,
    NasaFirmsProvider,
)
from app.environment.service import EnvironmentService  # noqa: E402
from app.environment.settings import EnvironmentSettings  # noqa: E402


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lng", type=float, required=True)
    parser.add_argument(
        "--json", action="store_true", help="Print the normalized context including provenance"
    )
    args = parser.parse_args()
    if not -90 <= args.lat <= 90 or not -180 <= args.lng <= 180:
        parser.error("Coordinates must be finite and within latitude/longitude bounds")
    load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)
    settings = EnvironmentSettings.from_env()
    async with httpx.AsyncClient(follow_redirects=False) as client:
        http = ProviderHTTP(client, settings.timeout_seconds)
        env = EnvironmentService(
            GoogleAirQualityProvider(http, settings.google_key.get_secret_value()),
            GoogleWeatherProvider(http, settings.google_key.get_secret_value()),
            NasaFirmsProvider(
                http, settings.firms_key.get_secret_value(), settings.firms_radius_km
            ),
            settings,
        )
        context = await env.context(args.lat, args.lng)
    if args.json:
        print(json.dumps(context.model_dump(mode="json"), indent=2))
    else:
        print(
            f"NCR probe {context.latitude}, {context.longitude} "
            f"at {context.requested_at.isoformat()}"
        )
        for name, status in context.source_statuses:
            print(
                f"{name:14} {status.status.value.upper():16} "
                f"{status.latency_ms:8.2f} ms | {status.message}"
            )
        if context.air_quality:
            print("AQ indexes:", [(i.code, i.value) for i in context.air_quality.indexes])
        if context.weather:
            print("Temperature:", context.weather.temperature)
        if context.fires is not None:
            print("Nearby active-fire detections:", len(context.fires))
        print("Use --json for normalized values, source timestamps, and provenance.")


if __name__ == "__main__":
    asyncio.run(main())
