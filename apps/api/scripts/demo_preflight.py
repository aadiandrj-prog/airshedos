"""Read-only local/demo preflight. --live performs genuine provider queries/cache warming."""

import argparse
import asyncio
import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[3]


def provider_check(name, source, latency_ms):
    state = source.get("status", "unavailable")
    return {
        "check": name,
        "result": "PASS" if state in ("live", "cached") else "WARN",
        "provider_status": state,
        "latency_ms": round(latency_ms, 2),
        "note": "Provider response only; availability is not evidence of a reported event.",
    }


async def inspect(client, api, web, live, latitude, longitude):
    rows = []

    async def fetch(name, url, json_response=True):
        start = time.perf_counter()
        try:
            response = await client.get(url)
            response.raise_for_status()
            value = response.json() if json_response else response.content
            if name in ("backend_health", "backend_ready"):
                expected = "ok" if name == "backend_health" else "ready"
                if not isinstance(value, dict) or value.get("status") != expected:
                    raise ValueError("Invalid health status")
            rows.append(
                {
                    "check": name,
                    "result": "PASS",
                    "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                }
            )
            return value
        except (httpx.HTTPError, ValueError):
            rows.append(
                {
                    "check": name,
                    "result": "FAIL",
                    "note": "Unavailable or invalid response; no raw errors retained.",
                }
            )
            return None

    await asyncio.gather(
        fetch("backend_health", api + "/health"),
        fetch("backend_ready", api + "/ready"),
        fetch("frontend_health", web, False),
        fetch("synthetic_fixture", web + "/demo/open-burning.png", False),
    )
    sources = await fetch("backend_configuration_endpoint", api + "/api/v1/environment/sources")
    if sources:
        for name, value in sources.items():
            rows.append(
                {
                    "check": name + "_configuration",
                    "result": "PASS" if value.get("configured") else "WARN",
                    "note": "Backend configuration presence only; not credential validation.",
                }
            )
    if live:
        query = f"lat={latitude}&lng={longitude}"
        start = time.perf_counter()
        ground, satellite, forecast = await asyncio.gather(
            fetch(
                "ground_context_request",
                api + "/api/v1/environment/context?include_satellite=false&" + query,
            ),
            fetch("satellite_request", api + "/api/v1/environment/satellite?" + query),
            fetch("forecast_request", api + "/api/v1/environment/forecast?" + query),
        )
        if ground:
            for name, source in ground["source_statuses"].items():
                rows.append(provider_check(name, source, source["latency_ms"]))
        for name, value in (("earth_engine", satellite), ("google_aq_forecast", forecast)):
            if value:
                source = value["provider_status"]
                row = provider_check(name, source, source["latency_ms"])
                if name == "earth_engine":
                    row["products"] = [
                        {"product": p["product"], "availability": p["availability"]}
                        for p in value["products"]
                    ]
                rows.append(row)
        rows.append(
            {
                "check": "parallel_provider_gate",
                "result": "PASS" if all((ground, satellite, forecast)) else "WARN",
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
                "note": "Transport completion; consult each provider's genuine status above.",
            }
        )
    return rows


def config_checks(values):
    project = values.get("GOOGLE_CLOUD_PROJECT")
    return [
        {"check": name, "result": "PASS" if present else "WARN", "note": note}
        for name, present, note in (
            (
                "gemini_configuration",
                bool(project),
                "Local project presence only; real rehearsal verifies ADC/model access.",
            ),
            (
                "earth_engine_configuration",
                bool(values.get("EARTH_ENGINE_PROJECT") or project),
                "Local project presence only; --live verifies remote access.",
            ),
            (
                "maps_browser_configuration",
                bool(values.get("NEXT_PUBLIC_GOOGLE_MAPS_BROWSER_KEY")),
                "Local key presence only; verify origins in a browser. Rebuild after changes.",
            ),
        )
    ]


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--web", default="http://localhost:3000")
    parser.add_argument("--lat", type=float, default=28.52)
    parser.add_argument("--lng", type=float, default=77.08)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    for url in (args.api, args.web):
        parsed = urlparse(url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            parser.error("Use an HTTP(S) origin without embedded credentials")
    if not (-90 <= args.lat <= 90 and -180 <= args.lng <= 180):
        parser.error("Invalid coordinates")
    values = {**dotenv_values(ROOT / ".env"), **os.environ}
    async with httpx.AsyncClient(timeout=40, follow_redirects=False) as client:
        rows = await inspect(
            client, args.api.rstrip("/"), args.web.rstrip("/"), args.live, args.lat, args.lng
        )
    rows.extend(config_checks(values))
    try:
        probe = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, timeout=5
        )
        rows.append(
            {
                "check": "docker_engine",
                "result": "PASS" if probe.returncode == 0 else "WARN",
                "note": "Engine detection only; HTTP health checks verify the applications.",
            }
        )
    except (OSError, subprocess.TimeoutExpired):
        rows.append(
            {
                "check": "docker_engine",
                "result": "WARN",
                "note": "Not detectable; native services may still be healthy.",
            }
        )
    overall = (
        "FAIL"
        if any(r["result"] == "FAIL" for r in rows)
        else "WARN"
        if any(r["result"] == "WARN" for r in rows)
        else "PASS"
    )
    result = {
        "status": overall,
        "captured_at": datetime.now(UTC).isoformat(),
        "live_queries": args.live,
        "latitude": args.lat,
        "longitude": args.lng,
        "checks": rows,
        "note": "Local configuration only. No credential changes or Gemini inference.",
    }
    output = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n")
    print(output)
    return 1 if overall == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
