import argparse
import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from prediction.availability import DEFAULT_AQ_BUFFER_HOURS, OPERATIONAL_V1, RESEARCH_ENRICHED_V1
from prediction.common import DatasetError, RawCache, hourly, write_json
from prediction.evaluation import baselines, validate
from prediction.frame import FrameConfig
from prediction.openaq import OpenAQ
from prediction.pipeline import build, discover, load_artifacts, verify_real_feasibility
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
        parser.add_argument(
            "--profile", choices=[OPERATIONAL_V1, RESEARCH_ENRICHED_V1], default=OPERATIONAL_V1
        )
        parser.add_argument("--aq-availability-buffer-hours", type=int)
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
    era5 = None
    started_at, started = datetime.now(UTC), time.monotonic()
    succeeded = False
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
            buffer = args.aq_availability_buffer_hours
            if buffer is None:
                buffer = int(os.getenv("AQ_AVAILABILITY_BUFFER_HOURS", DEFAULT_AQ_BUFFER_HOURS))
            config = FrameConfig(
                args.start, args.end, profile=args.profile, aq_availability_buffer_hours=buffer
            )
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
                verify_real_feasibility(args.gate_directory)
                if (hourly(config.end) - hourly(config.start)).days < 90 or len(stations) < 2:
                    raise DatasetError(
                        "Full frame needs at least 90 days and two coverage-selected stations"
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
                feature_availability=json.loads(
                    (args.output / "feature_availability_manifest.json").read_text()
                ),
            )
            if action == "validate":
                write_json(args.output / "leakage_report.json", report)
                print(json.dumps(report))
            else:
                metrics = {"synthetic": manifest["synthetic"], **baselines(frame, frozen)}
                write_json(args.output / "baseline_metrics.json", metrics)
                print(json.dumps(metrics))
        succeeded = True
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
        write_json(
            args.output / "runs" / f"{action}-{started_at.strftime('%Y%m%dT%H%M%S%f')}.json",
            {
                "action": action,
                "started_at": started_at.isoformat(),
                "status": "pass" if succeeded else "failed",
                "elapsed_seconds": time.monotonic() - started,
                "openaq_requests": api.requests if api else 0,
                "earth_engine_rpcs": era5.requests if era5 else 0,
                "source_cache_hits": cache.hits,
                "source_cache_misses": cache.misses,
                "response_metadata": api.response_metadata if api else [],
            },
        )
        if api:
            api.close()
    return 0
