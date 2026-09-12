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
    parser.add_argument(
        "--gate",
        action="store_true",
        help="Also verify cache reuse and a local weather-disabled partial response",
    )
    args = parser.parse_args()
    if not -90 <= args.lat <= 90 or not -180 <= args.lng <= 180:
        parser.error("Coordinates must be finite and within latitude/longitude bounds")
    load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)
    settings = EnvironmentSettings.from_env()
    http_responses = []

    async def record_response(response):
        # Deliberately record only allowlisted provider identity and HTTP status.
        names = {
            "airquality.googleapis.com": "google_air_quality",
            "weather.googleapis.com": "google_weather",
            "firms.modaps.eosdis.nasa.gov": "nasa_firms",
        }
        http_responses.append(
            {
                "provider": names.get(response.request.url.host, "unknown"),
                "http_status": response.status_code,
            }
        )

    gate = None
    async with httpx.AsyncClient(
        follow_redirects=False, event_hooks={"response": [record_response]}
    ) as client:
        http = ProviderHTTP(client, settings.timeout_seconds)
        env = EnvironmentService(
            GoogleAirQualityProvider(http, settings.google_key.get_secret_value()),
            GoogleWeatherProvider(http, settings.google_key.get_secret_value()),
            NasaFirmsProvider(
                http,
                settings.firms_key.get_secret_value(),
                settings.firms_radius_km,
                settings.firms_dataset,
            ),
            settings,
        )
        context = await env.context(args.lat, args.lng)
        if args.gate:
            request_count = len(http_responses)
            cached = await env.context(args.lat, args.lng)

            def observations(result):
                values = [result.air_quality, result.weather, *(result.fires or [])]
                return [v.model_dump(exclude={"status"}) for v in values if v is not None]

            cache_pass = (
                all(s.status == "live" for _, s in context.source_statuses)
                and all(s.status == "cached" for _, s in cached.source_statuses)
                and request_count == len(http_responses)
                and observations(context) == observations(cached)
                and context.fire_dataset == cached.fire_dataset
                and all(
                    source.retrieved_at == getattr(cached.source_statuses, name).retrieved_at
                    for name, source in context.source_statuses
                )
            )
            # Only this local service is changed; .env and external services are untouched.
            original_weather = env.providers["weather"]
            env.providers["weather"] = GoogleWeatherProvider(http, "")
            try:
                degraded = await env.context(args.lat, args.lng)
            finally:
                env.providers["weather"] = original_weather
            partial_pass = (
                degraded.source_statuses.weather.status == "not_configured"
                and degraded.weather is None
                and degraded.source_statuses.air_quality.status == "cached"
                and degraded.source_statuses.fires.status == "cached"
                and degraded.air_quality == cached.air_quality
                and degraded.fires == cached.fires
                and request_count == len(http_responses)
            )
            gate = {
                "provider_http_responses": http_responses,
                "outbound_responses_after_first": request_count,
                "outbound_responses_after_cache_and_degraded": len(http_responses),
                "cache_pass": cache_pass,
                "cache_source_statuses": cached.source_statuses.model_dump(mode="json"),
                "cache_requested_at": cached.requested_at.isoformat(),
                "provenance_and_observation_times_unchanged": observations(context)
                == observations(cached),
                "partial_failure_pass": partial_pass,
                "degraded_source_statuses": degraded.source_statuses.model_dump(mode="json"),
                "degraded_requested_at": degraded.requested_at.isoformat(),
                "gate_pass": cache_pass and partial_pass,
            }
    if args.json:
        output = context.model_dump(mode="json")
        if gate is not None:
            output = {"first_context": output, "verification": gate}
        print(json.dumps(output, indent=2))
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
        if gate is not None:
            print("Cache verification:", "PASS" if gate["cache_pass"] else "FAIL")
            print("Controlled partial failure:", "PASS" if gate["partial_failure_pass"] else "FAIL")
            print(
                "Outbound responses (first/final):",
                gate["outbound_responses_after_first"],
                gate["outbound_responses_after_cache_and_degraded"],
            )
        print("Use --json for normalized values, source timestamps, and provenance.")
    if gate is not None and not gate["gate_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
