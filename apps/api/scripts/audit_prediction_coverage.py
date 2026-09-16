"""Inventory every NCR PM2.5 sensor and measure a common window, after real feasibility."""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from prediction.common import DatasetError, RawCache, hourly, write_json  # noqa: E402
from prediction.coverage import coverage_report, select_stations  # noqa: E402
from prediction.openaq import PM_UNITS, OpenAQ  # noqa: E402
from prediction.pipeline import verify_real_feasibility  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/live_acceptance/coverage_2025")
    )
    parser.add_argument("--cache", type=Path, default=Path("data/cache/prediction_v1"))
    parser.add_argument("--start", default="2025-01-01T00:00:00Z")
    parser.add_argument("--end", default="2026-01-01T00:00:00Z")
    parser.add_argument("--gate-directory", type=Path)
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if not args.metadata_only:
        if args.gate_directory is None:
            parser.error("Measured common-window audit requires a real feasibility gate")
        verify_real_feasibility(args.gate_directory)
    api = OpenAQ(os.getenv("OPENAQ_API_KEY", ""), RawCache(args.cache))
    started = time.monotonic()
    inventory, reports = [], []
    try:
        locations = api.locations()
        write_json(args.output / "locations.json", locations)
        for location in locations:
            for sensor in location["sensors"]:
                if (
                    sensor["parameter"]["name"] != "pm25"
                    or sensor["parameter"]["units"] not in PM_UNITS
                ):
                    continue
                sensor = api.sensor(sensor["id"])
                first, last = sensor.get("datetimeFirst"), sensor.get("datetimeLast")
                overlap = (
                    max(
                        0,
                        (
                            min(pd.Timestamp(last["utc"]), hourly(args.end))
                            - max(pd.Timestamp(first["utc"]), hourly(args.start))
                        ).total_seconds()
                        / 86400,
                    )
                    if first and last
                    else 0
                )
                item = {
                    "station_id": str(location["id"]),
                    "name": location.get("name"),
                    "coordinates": location["coordinates"],
                    "timezone": location["timezone"],
                    "provider": location.get("provider"),
                    "instruments": location.get("instruments"),
                    "sensor": sensor,
                    "metadata_overlap_days": overlap,
                    "assessment": "metadata_only" if args.metadata_only else "no_90_day_overlap",
                }
                if not args.metadata_only and overlap >= 90:
                    aq = api.hours(location["id"], sensor, args.start, args.end)
                    destination = args.output / "normalized" / f"sensor_{sensor['id']}.parquet"
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    aq.to_parquet(destination, index=False)
                    expected = [
                        {
                            "station_id": str(location["id"]),
                            "sensor_id": sensor["id"],
                            "pollutant": "pm25",
                            "unit": "µg/m³",
                        }
                    ]
                    report = coverage_report(aq, args.start, args.end, expected)
                    reports.append(report)
                    item.update(
                        assessment="hourly_measured",
                        returned_hourly_rows=len(aq),
                        usable_hourly_rows=int(aq.value.notna().sum()),
                    )
                    pd.concat(reports).to_csv(args.output / "candidate_coverage.csv", index=False)
                    print(
                        json.dumps(
                            {
                                "station": location["id"],
                                "sensor": sensor["id"],
                                "measured_candidates": len(reports),
                                "returned_rows": len(aq),
                                "usable_rows": item["usable_hourly_rows"],
                                "requests": api.requests,
                            }
                        ),
                        flush=True,
                    )
                inventory.append(item)
                write_json(args.output / "candidate_inventory.json", inventory)
        if reports:
            coverage = pd.concat(reports, ignore_index=True)
            selected = select_stations(locations, coverage, count=5)
            write_json(args.output / "selected_stations.json", selected)
        write_json(
            args.output / "source_manifest.json", {"sources": list(api.cache.references.values())}
        )
        write_json(
            args.output / "audit_summary.json",
            {
                "start": args.start,
                "end": args.end,
                "locations": len(locations),
                "pm25_sensors": len(inventory),
                "measured_sensors": len(reports),
                "requests": api.requests,
                "cache_hits": api.cache.hits,
                "elapsed_seconds": time.monotonic() - started,
                "response_metadata": api.response_metadata,
                "selected_stations": selected if reports else [],
            },
        )
    except DatasetError as exc:
        write_json(
            args.output / "last_failure.json",
            {
                "status": "failed",
                "reason": str(exc),
                "requests": api.requests,
                "elapsed_seconds": time.monotonic() - started,
            },
        )
        print(json.dumps({"status": "failed", "reason": str(exc)}))
        return 2
    finally:
        api.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
