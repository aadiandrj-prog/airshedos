import json
import logging
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from prediction.common import (
    ERA5_BANDS,
    ERA5_COLLECTION,
    POLLUTANTS,
    VERSION,
    DatasetError,
    digest,
    hourly,
    write_json,
)
from prediction.coverage import coverage_report, select_stations
from prediction.evaluation import baselines, holdout_plan, target_analysis, validate
from prediction.frame import (
    apply_spike_rule,
    construct,
    freeze_spike_rule,
    split_boundaries,
)
from prediction.openaq import PM_UNITS, deduplicate

logger = logging.getLogger(__name__)


def discover(api, start, end, output, max_candidates=12, count=5, feasibility=False):
    locations = api.locations()
    candidates, metadata = [], []
    # Metadata screening before any multi-month download. No station-name hardcoding.
    for location in locations:
        sensors = []
        for brief in location["sensors"]:
            if brief["parameter"]["name"] != "pm25" or brief["parameter"]["units"] not in PM_UNITS:
                continue
            sensor = api.sensor(brief["id"])
            metadata.append({"station_id": str(location["id"]), "sensor": sensor})
            first, last = sensor.get("datetimeFirst"), sensor.get("datetimeLast")
            if first and last:
                overlap = min(pd.Timestamp(last["utc"]), hourly(end)) - max(
                    pd.Timestamp(first["utc"]), hourly(start)
                )
                if overlap >= pd.Timedelta(days=7 if feasibility else 90):
                    sensors.append(sensor)
        if sensors:
            candidates.append((location, sensors))
    # More metadata overlap first; tie by station ID, explicitly report the download budget.
    candidates.sort(
        key=lambda item: (
            -max(
                (
                    min(pd.Timestamp(s["datetimeLast"]["utc"]), hourly(end))
                    - max(pd.Timestamp(s["datetimeFirst"]["utc"]), hourly(start))
                ).total_seconds()
                for s in item[1]
            ),
            item[0]["id"],
        )
    )
    frames = []
    evaluated = []
    for location, sensors in candidates[:max_candidates]:
        evaluated.append(location)
        for sensor in sensors:
            frames.append(api.hours(location["id"], sensor, start, end))
    if not frames:
        write_json(
            Path(output) / "discovery_manifest.json",
            {
                "status": "no_eligible_metadata_overlap",
                "locations": locations,
                "sensor_metadata": metadata,
            },
        )
        raise DatasetError(
            "No candidate has the required metadata overlap; inspect discovery"
            " before choosing an earlier window"
        )
    aq = deduplicate(pd.concat(frames, ignore_index=True))
    expected = [
        {
            "station_id": str(location["id"]),
            "sensor_id": sensor["id"],
            "pollutant": "pm25",
            "unit": "µg/m³",
        }
        for location, sensors in candidates[:max_candidates]
        for sensor in sensors
    ]
    coverage = coverage_report(aq, start, end, expected)
    selected = select_stations(evaluated, coverage, count=count, min_months=1 if feasibility else 3)
    Path(output).mkdir(parents=True, exist_ok=True)
    coverage.to_csv(Path(output) / "candidate_coverage.csv", index=False)
    write_json(
        Path(output) / "discovery_manifest.json",
        {
            "start": start,
            "end": end,
            "mode": "feasibility" if feasibility else "full",
            "metadata_locations": len(locations),
            "candidate_locations_with_overlap": len(candidates),
            "evaluated_locations": evaluated,
            "sensor_metadata": metadata,
            "max_candidates": max_candidates,
            "selection": (
                "actual hourly coverage >=80%, >=3 well-covered months for full "
                "build; one PM2.5 sensor per location"
            ),
            "selected_stations": selected,
            "not_evaluated_due_to_budget": [
                str(location["id"]) for location, _ in candidates[max_candidates:]
            ],
            "openaq_requests": api.requests,
            "cache_hits": api.cache.hits,
        },
    )
    if len(selected) < (2 if feasibility else 3):
        raise DatasetError(
            "Too few stations meet measured common-period coverage; inspect "
            "the report and choose a documented fallback window"
        )
    write_json(Path(output) / "selected_stations.json", selected)
    return selected


def build(api, era5, stations, config, output, retrospective=False, synthetic=False):
    if not retrospective:
        raise DatasetError(
            "ERA5 at t is not known at t. Use --retrospective-research for a "
            "clearly labeled research frame; strict operational readiness "
            "remains blocked."
        )
    started = time.monotonic()
    start = hourly(config.start) - pd.Timedelta(days=30)
    end = hourly(config.end)
    if not stations or len({str(s["id"]) for s in stations}) != len(stations):
        raise DatasetError("Selected station IDs must be nonempty and unique")
    frames, sensor_manifest = [], []
    for station in stations:
        selected_ids = dict(station.get("selected_sensor_ids", {}))
        selected_ids["pm25"] = station["pm25_sensor_id"]
        # Optional sensor chosen deterministically; never combine multiple instruments or units.
        for pollutant in POLLUTANTS:
            choices = sorted(
                [s for s in station["sensors"] if s["parameter"]["name"] == pollutant],
                key=lambda s: s["id"],
            )
            if not choices:
                if pollutant == "pm25":
                    raise DatasetError("Selected station has no PM2.5 sensor")
                continue
            if pollutant in selected_ids and not any(
                s["id"] == selected_ids[pollutant] for s in choices
            ):
                raise DatasetError("Selected sensor is absent from station metadata")
            choice = next(
                (s for s in choices if s["id"] == selected_ids.get(pollutant)), choices[0]
            )
            sensor_manifest.append(
                {
                    "station_id": str(station["id"]),
                    "sensor": choice,
                    "selection": "coverage-selected PM2.5; lowest-ID optional sensor; no blending",
                }
            )
            frames.append(api.hours(station["id"], choice, start, end))
    aq = deduplicate(pd.concat(frames, ignore_index=True))
    # Check actual requested-period AQ before spending Earth Engine queries.
    locations = [
        {
            **station,
            "coordinates": {"latitude": station["latitude"], "longitude": station["longitude"]},
        }
        for station in stations
    ]
    coverage = coverage_report(aq, config.start, config.end)
    min_months = 3 if hourly(config.end) - hourly(config.start) >= pd.Timedelta(days=90) else 1
    qualified = select_stations(locations, coverage, count=len(stations), min_months=min_months)
    if {s["id"] for s in qualified} != {str(s["id"]) for s in stations}:
        Path(output).mkdir(parents=True, exist_ok=True)
        coverage.to_csv(Path(output) / "station_coverage.csv", index=False)
        raise DatasetError("Selected stations fail measured coverage in requested build window")
    weather = era5.extract(stations, start, end)
    return write_artifacts(
        aq,
        weather,
        stations,
        config,
        output,
        sensor_manifest,
        cache=api.cache,
        stats={
            "openaq_requests": api.requests,
            "earth_engine_rpcs": era5.requests,
            "elapsed_seconds": time.monotonic() - started,
        },
        synthetic=synthetic,
    )


def write_artifacts(
    aq, weather, stations, config, output, sensors, cache=None, stats=None, synthetic=False
):
    started = time.monotonic()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    frame, features = construct(aq, weather, stations, config)
    frozen = freeze_spike_rule(frame)
    frame = apply_spike_rule(frame, frozen)
    leakage = validate(frame, aq, weather, stations, config, features, frozen)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = "unknown", True
    manifest = {
        "version": VERSION,
        "build_timestamp": datetime.now(UTC).isoformat(),
        "dataset_mode": leakage["dataset_mode"],
        "synthetic": synthetic,
        "ready_for_operational_training": False,
        "config": config.to_dict(),
        "stations": stations,
        "sensors": sensors,
        "era5_collection": ERA5_COLLECTION,
        "era5_band_units": ERA5_BANDS,
        "fire_features": "deferred: daily raster lacks exact detection/availability times",
        "satellite_features": "deferred: asynchronous optional ablation; no backfill",
        "features": features,
        "feature_definitions": {
            "canonical_key": "station_id + UTC interval-end timestamp",
            "pm25_t": "hour ending at t; µg/m³; >=75% source hourly coverage",
            "pm25_lag_Nh": "same-station value exactly t-N hours; µg/m³",
            "pm25_rolling_mean_Nh": "all N hours [t-(N-1),t]; µg/m³; missing if incomplete",
            "pm25_rolling_std_Nh": "population std ddof=0 over same full window; µg/m³",
            "trailing_30d_pXX_pm25": "quantile over (t-30d,t]; >=576/720 hours; µg/m³",
            "history_count_30d": "observed usable hours in (t-30d,t]",
            "calendar": "hour_of_day/day_of_week/month/weekend in recorded station timezone",
            "optional_pollutant": "current and lag_1h; unit encoded in column; no conversion",
            "era5": "source bands at t; native units below; retrospective publication",
            "era5_wind_speed_mps": "hypot(u10,v10); m/s",
            "era5_wind_from_degrees": "atan2(-u10,-v10) modulo 360; calm is missing",
        },
        "targets": {
            "future_max_pm25_6h": "same-station max of all t+1..t+6, µg/m³",
            "future_mean_pm25_6h": "same-station mean of all t+1..t+6, µg/m³",
            "spike_next_6h": frozen,
        },
        "rows": len(frame),
        "raw_aq_rows": len(aq),
        "raw_usable_pm25_rows": int(((aq.pollutant == "pm25") & aq.value.notna()).sum()),
        "regression_eligible_rows": int(
            (frame.regression_eligible & (frame.split != "purged")).sum()
        ),
        "missing_fraction": {c: float(frame[c].isna().mean()) for c in features},
        "split_boundaries": split_boundaries(config),
        "code_git_commit": commit,
        "code_worktree_dirty": dirty,
        "runtime": {**(stats or {}), "frame_seconds": time.monotonic() - started},
        "limitations": leakage["operational_blockers"]
        + [
            "NCR-specific; monitors do not represent every street.",
            "ERA5 is coarse regional reanalysis, not a collocated weather station.",
            "Spike is an operational heuristic, not a regulatory or epidemiological definition.",
            "No causal fire attribution; future models need prospective validation.",
        ],
    }
    aq.to_parquet(output / "normalized_aq.parquet", index=False)
    weather.to_parquet(output / "normalized_era5.parquet", index=False)
    frame.to_parquet(output / "prediction_frame.parquet", index=False)
    coverage_report(aq, config.start, config.end).to_csv(
        output / "station_coverage.csv", index=False
    )
    import hashlib

    manifest["artifact_sha256"] = {
        name: hashlib.sha256((output / name).read_bytes()).hexdigest()
        for name in ("normalized_aq.parquet", "normalized_era5.parquet", "prediction_frame.parquet")
    }
    manifest["contract_sha256"] = digest(
        {
            key: manifest[key]
            for key in ("config", "stations", "features", "targets", "artifact_sha256", "synthetic")
        }
    )
    write_json(output / "dataset_manifest.json", manifest)
    write_json(
        output / "source_manifest.json",
        {
            "sensors": sensors,
            "sources": list(cache.references.values()) if cache else [],
            "publication_time_note": (
                "retrieved_at is not historical available_at; absent release "
                "metadata remains unknown"
            ),
        },
    )
    write_json(
        output / "split_manifest.json",
        {**split_boundaries(config), "station_holdout": holdout_plan(stations, config)},
    )
    write_json(output / "target_analysis.json", target_analysis(frame, frozen))
    write_json(
        output / "baseline_metrics.json", {"synthetic": synthetic, **baselines(frame, frozen)}
    )
    write_json(output / "leakage_report.json", leakage)
    return manifest


def load_artifacts(directory):
    path = Path(directory)
    manifest = json.loads((path / "dataset_manifest.json").read_text())
    import hashlib

    for name in ("normalized_aq.parquet", "normalized_era5.parquet", "prediction_frame.parquet"):
        actual = hashlib.sha256((path / name).read_bytes()).hexdigest()
        if actual != manifest["artifact_sha256"].get(name):
            raise DatasetError("Artifact checksum mismatch; rebuild or restore snapshot")
    contract = digest(
        {
            key: manifest[key]
            for key in ("config", "stations", "features", "targets", "artifact_sha256", "synthetic")
        }
    )
    if contract != manifest["contract_sha256"]:
        raise DatasetError("Dataset contract checksum mismatch")
    return (
        manifest,
        pd.read_parquet(path / "prediction_frame.parquet"),
        pd.read_parquet(path / "normalized_aq.parquet"),
        pd.read_parquet(path / "normalized_era5.parquet"),
    )
