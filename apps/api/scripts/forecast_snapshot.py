"""Developer-only prospective snapshots. Explicit one-shot local API reads; no polling."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.environment.forecast_models import AirQualityForecastContext  # noqa: E402
from app.environment.models import AirQualityObservation  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def pm25(pollutants):
    return next(
        (p.concentration.model_dump() for p in pollutants if p.code == "pm25" and p.concentration),
        None,
    )


def snapshot(context: AirQualityForecastContext):
    if not context.hourly_forecasts or context.retrieved_at is None:
        raise ValueError("No provider forecast to record")
    return {
        "schema": "prospective_google_forecast_v1",
        "latitude": context.latitude,
        "longitude": context.longitude,
        "recorded_at": datetime.now(UTC).isoformat(),
        "retrieved_at": context.retrieved_at.isoformat(),
        "issued_at": None,  # Provider does not expose model issuance time.
        "provider": context.provider,
        "provenance": context.provenance.model_dump(mode="json"),
        "hourly": [
            {
                "forecast_at": h.forecast_at.isoformat(),
                "pm25": pm25(h.pollutants),
                "cpcb_aqi": next((i.value for i in h.indexes if i.code == "ind_cpcb"), None),
            }
            for h in context.hourly_forecasts
        ],
        "limitation": "Prospective paired provider outputs only; no independent accuracy claim.",
    }


def match_observation(saved, observed: AirQualityObservation):
    if (observed.latitude, observed.longitude) != (saved["latitude"], saved["longitude"]):
        raise ValueError("Coordinates differ")
    if observed.observed_at <= max(
        datetime.fromisoformat(saved["retrieved_at"]),
        datetime.fromisoformat(saved["recorded_at"]),
    ):
        raise ValueError("Observation must follow forecast retrieval and snapshot recording")
    target = next(
        (
            h
            for h in saved["hourly"]
            if datetime.fromisoformat(h["forecast_at"]) == observed.observed_at
        ),
        None,
    )
    if target is None:
        raise ValueError("No exact forecast-valid timestamp match; no interpolation")
    return {
        "schema": "prospective_google_observation_match_v1",
        "forecast_retrieved_at": saved["retrieved_at"],
        "forecast": target,
        "observed_at": observed.observed_at.isoformat(),
        "observation_retrieved_at": observed.retrieved_at.isoformat(),
        "latitude": observed.latitude,
        "longitude": observed.longitude,
        "pm25": pm25(observed.pollutants),
        "provenance": observed.provenance.model_dump(mode="json"),
        "provider": "google_air_quality",
        "limitation": "Same provider ecosystem; not an independent ground-truth validation.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["record", "match"])
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--lat", type=float, default=28.4595)
    parser.add_argument("--lng", type=float, default=77.0266)
    args = parser.parse_args()
    directory = ROOT / "data/forecast-evaluation"
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.Client(base_url="http://127.0.0.1:8000", timeout=60) as client:
            if args.mode == "record":
                response = client.get(
                    "/api/v1/environment/forecast", params={"lat": args.lat, "lng": args.lng}
                )
                response.raise_for_status()
                result = snapshot(AirQualityForecastContext.model_validate(response.json()))
            else:
                if args.snapshot is None or not args.snapshot.resolve().is_relative_to(directory):
                    raise ValueError("Select a snapshot under data/forecast-evaluation")
                saved = json.loads(args.snapshot.read_text())
                response = client.get(
                    "/api/v1/environment/context",
                    params={
                        "lat": saved["latitude"],
                        "lng": saved["longitude"],
                        "include_satellite": False,
                    },
                )
                response.raise_for_status()
                result = match_observation(
                    saved, AirQualityObservation.model_validate(response.json()["air_quality"])
                )
        path = directory / f"{args.mode}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}.json"
        with path.open("x") as stream:
            json.dump(result, stream, indent=2)
        print(f"Recorded {path.relative_to(ROOT)}. No accuracy claim.")
    except (ValueError, httpx.HTTPError, KeyError):
        print(
            "No snapshot written: unavailable data, invalid input, or no exact prospective match."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
