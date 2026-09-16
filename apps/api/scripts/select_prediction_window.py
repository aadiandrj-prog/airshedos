"""Choose the longest supported common window from a completed measured audit; no network."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from prediction.common import DatasetError, hourly, write_json  # noqa: E402
from prediction.coverage import coverage_report, select_stations  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = json.loads((args.audit / "audit_summary.json").read_text())
    inventory = json.loads((args.audit / "candidate_inventory.json").read_text())
    start, end = hourly(summary["start"]), hourly(summary["end"])
    locations, frames = [], []
    for item in inventory:
        if item["assessment"] != "hourly_measured":
            continue
        locations.append(
            {
                "id": item["station_id"],
                "name": item["name"],
                "coordinates": item["coordinates"],
                "timezone": item["timezone"],
                "provider": item["provider"],
                "instruments": item["instruments"],
            }
        )
        frames.append(
            pd.read_parquet(args.audit / "normalized" / f"sensor_{item['sensor']['id']}.parquet")
        )
    if len(frames) < 2 or len(frames) != summary["measured_sensors"]:
        raise DatasetError("Completed audit and measured source snapshots disagree")
    # Full location metadata carries optional sensor identities; the audit records it once.
    source_locations = json.loads((args.audit / "locations.json").read_text())
    locations = [s for s in source_locations if str(s["id"]) in {s["id"] for s in locations}]
    aq = pd.concat(frames, ignore_index=True)
    bounds = aq[aq.value.notna()].groupby(["station_id", "sensor_id"]).timestamp.agg(["min", "max"])
    # Keep the preferred year end. Candidates are observed series starts rounded UP to
    # a complete UTC day. No search over label prevalence, baselines or model accuracy.
    starts = sorted({start, *[max(start, value.ceil("D")) for value in bounds["min"]]})
    evaluated = []
    for candidate_start in starts:
        if (end - candidate_start).days < 90:
            continue
        coverage = coverage_report(aq, candidate_start, end)
        selected = select_stations(locations, coverage, count=5)
        if candidate_start != start:
            # Exclude series that start after the proposed common window begins.
            supported = {
                str(sid)
                for (sid, sensor), row in bounds.iterrows()
                if row["min"] <= candidate_start + pd.Timedelta(hours=1)
            }
            selected = select_stations(
                [s for s in locations if str(s["id"]) in supported],
                coverage[coverage.station_id.isin(supported)],
                count=5,
            )
        evaluated.append(
            {
                "start": candidate_start.isoformat(),
                "end": end.isoformat(),
                "qualifying_selected_stations": len(selected),
            }
        )
        if len(selected) >= 2:
            args.output.mkdir(parents=True, exist_ok=True)
            coverage.to_csv(args.output / "candidate_coverage.csv", index=False)
            write_json(args.output / "selected_stations.json", selected)
            write_json(
                args.output / "window_selection.json",
                {
                    "start": candidate_start.isoformat(),
                    "end": end.isoformat(),
                    "days": (end - candidate_start).days,
                    "evaluated_windows": evaluated,
                    "reason": "Earliest supported common start within the preferred audited year; "
                    ">=80% usable hours and >=3 covered months; quality before spread.",
                    "not_claimed": "Periods outside audited 2025 were not assessed.",
                    "requests": 0,
                },
            )
            print(
                json.dumps(
                    {
                        "start": str(candidate_start),
                        "end": str(end),
                        "selected": [s["id"] for s in selected],
                    }
                )
            )
            return 0
    write_json(
        args.output / "window_selection.json",
        {"status": "insufficient_coverage", "evaluated_windows": evaluated},
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
