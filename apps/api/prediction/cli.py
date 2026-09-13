import argparse
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from prediction.common import DatasetError, RawCache, hourly, write_json
from prediction.evaluation import baselines, validate
from prediction.frame import FrameConfig
from prediction.openaq import OpenAQ
from prediction.pipeline import build, discover, load_artifacts
from prediction.weather import ERA5

ROOT = Path(__file__).resolve().parents[3]


def main(action):
    parser = argparse.ArgumentParser(description=f"AirshedOS offline prediction dataset: {action}")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/prediction_v1")
    parser.add_argument("--cache", type=Path, default=ROOT / "data/cache/prediction_v1")
    if action in {"discover", "build"}:
        parser.add_argument("--start", default="2025-01-01T00:00:00Z")
        parser.add_argument("--end", default="2026-01-01T00:00:00Z")
        parser.add_argument("--feasibility", action="store_true")
    if action == "discover":
        parser.add_argument("--max-candidates", type=int, default=12)
        parser.add_argument("--count", type=int, default=5)
    if action == "build":
        parser.add_argument("--stations", type=Path, required=True)
        parser.add_argument("--retrospective-research", action="store_true")
        parser.add_argument("--gate-directory", type=Path)
    if action == "validate":
        parser.add_argument("--require-operational", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Never expose auth headers or credential-bearing URLs through HTTP client debug logging.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    cache = RawCache(args.cache)
    api = None
    try:
        if action in {"discover", "build"}:
            api = OpenAQ(os.getenv("OPENAQ_API_KEY", ""), cache)
        if action == "discover":
            if not 2 <= args.count <= 5 or not 2 <= args.max_candidates <= 50:
                raise DatasetError("Select 2–5 stations and inspect at most 50 candidate locations")
            selected = discover(
                api,
                args.start,
                args.end,
                args.output,
                args.max_candidates,
                args.count,
                args.feasibility,
            )
            print(
                json.dumps(
                    {
                        "selected": [
                            {"id": s["id"], "name": s["name"], "reason": s["selection_reason"]}
                            for s in selected
                        ]
                    }
                )
            )
        elif action == "build":
            config = FrameConfig(args.start, args.end)
            stations = json.loads(args.stations.read_text())
            if not isinstance(stations, list) or not 2 <= len(stations) <= 5:
                raise DatasetError("Build requires 2–5 selected stations")
            days_requested = (hourly(config.end) - hourly(config.start)).total_seconds() / 86400
            if args.feasibility and (not 14 <= days_requested <= 31 or len(stations) < 2):
                raise DatasetError("Feasibility build requires 2–4 weeks and at least two stations")
            if not args.feasibility:
                if args.gate_directory is None:
                    raise DatasetError(
                        "Full build requires --gate-directory from a real multi-week, two-"
                        "station feasibility build"
                    )
                gate, gate_frame, aq, weather = load_artifacts(args.gate_directory)
                if (
                    gate.get("synthetic") is not False
                    or len(gate["stations"]) < 2
                    or gate["regression_eligible_rows"] < 24
                    or weather.empty
                    or set(weather.station_id.astype(str))
                    != {str(s["id"]) for s in gate["stations"]}
                ):
                    raise DatasetError(
                        "Feasibility gate must contain real multi-station data and usable targets"
                    )
                days = (hourly(gate["config"]["end"]) - hourly(gate["config"]["start"])).days
                if not 14 <= days <= 31:
                    raise DatasetError("Feasibility gate must cover 2–4 weeks")
                validate(
                    gate_frame,
                    aq,
                    weather,
                    gate["stations"],
                    FrameConfig(**gate["config"]),
                    gate["features"],
                    gate["targets"]["spike_next_6h"],
                )
                core = [
                    "era5_temperature_2m",
                    "era5_surface_pressure",
                    "era5_u_component_of_wind_10m",
                    "era5_v_component_of_wind_10m",
                ]
                for _, group in gate_frame.groupby("station_id"):
                    if (
                        group[core].notna().all(axis=1).mean() < 0.8
                        or group.regression_eligible.sum() < 24
                    ):
                        raise DatasetError(
                            "Feasibility needs >=80% core weather and targets per station"
                        )
                if (hourly(config.end) - hourly(config.start)).days < 90 or len(stations) < 3:
                    raise DatasetError(
                        "Full frame needs at least 90 days and three coverage-selected stations"
                    )
            era5 = ERA5(
                os.getenv("EARTH_ENGINE_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT"), cache
            )
            manifest = build(
                api, era5, stations, config, args.output, retrospective=args.retrospective_research
            )
            print(
                json.dumps(
                    {
                        "rows": manifest["rows"],
                        "regression_eligible_rows": manifest["regression_eligible_rows"],
                        "mode": manifest["dataset_mode"],
                    }
                )
            )
        else:
            manifest, frame, aq, weather = load_artifacts(args.output)
            frozen = manifest["targets"]["spike_next_6h"]
            report = validate(
                frame,
                aq,
                weather,
                manifest["stations"],
                FrameConfig(**manifest["config"]),
                manifest["features"],
                frozen,
                require_operational=action == "validate" and args.require_operational,
            )
            if action == "validate":
                write_json(args.output / "leakage_report.json", report)
                print(json.dumps(report))
            else:
                metrics = {"synthetic": manifest["synthetic"], **baselines(frame, frozen)}
                write_json(args.output / "baseline_metrics.json", metrics)
                print(json.dumps(metrics))
    except (DatasetError, OSError, ValueError) as exc:
        # DatasetError messages are deliberately sanitized; other failures can include paths only.
        message = (
            str(exc)
            if isinstance(exc, DatasetError)
            else "Artifact/configuration parsing failed; inspect local inputs."
        )
        write_json(
            args.output / "last_failure.json",
            {"action": action, "status": "blocked", "message": message},
        )
        print(json.dumps({"status": "blocked", "message": message}))
        return 2
    finally:
        if api:
            api.close()
    return 0
