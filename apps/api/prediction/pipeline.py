import json
import logging
import subprocess
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from prediction.availability import OPERATIONAL_V1, RESEARCH_ENRICHED_V1, availability_manifest
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
            "response_metadata": api.response_metadata,
        },
    )
    if len(selected) < 2:
        raise DatasetError(
            "Too few stations meet measured common-period coverage; inspect "
            "the report and choose a documented fallback window"
        )
    write_json(Path(output) / "selected_stations.json", selected)
    return selected


def build(api, era5, stations, config, output, retrospective=False, synthetic=False):
    if config.profile == RESEARCH_ENRICHED_V1 and not retrospective:
        raise DatasetError(
            "ERA5 at t is not known at t. Use --retrospective-research for a "
            "clearly labeled research frame; strict operational readiness "
            "remains blocked."
        )
    started = time.monotonic()
    buffer = config.aq_availability_buffer_hours if config.profile == OPERATIONAL_V1 else 0
    start = hourly(config.start) - pd.Timedelta(days=30, hours=buffer)
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
            if pollutant != "pm25" and pollutant not in selected_ids:
                ranked = []
                for candidate in choices:
                    metadata = api.sensor(candidate["id"])
                    first, last = metadata.get("datetimeFirst"), metadata.get("datetimeLast")
                    if first and last:
                        overlap = min(pd.Timestamp(last["utc"]), end) - max(
                            pd.Timestamp(first["utc"]), start
                        )
                        if overlap > pd.Timedelta(0):
                            ranked.append(
                                (overlap.total_seconds(), -int(candidate["id"]), metadata)
                            )
                if not ranked:
                    sensor_manifest.append(
                        {
                            "station_id": str(station["id"]),
                            "pollutant": pollutant,
                            "status": "no_sensor_metadata_overlap",
                        }
                    )
                    continue
                choices = [max(ranked, key=lambda item: item[:2])[2]]
            choice = next(
                (s for s in choices if s["id"] == selected_ids.get(pollutant)), choices[0]
            )
            sensor_manifest.append(
                {
                    "station_id": str(station["id"]),
                    "sensor": choice,
                    "selection": "PM2.5 coverage; optional sensor overlap; no blending",
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
    manifest = write_artifacts(
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
            "source_cache_hits": api.cache.hits,
            "source_cache_misses": api.cache.misses,
            "response_metadata": api.response_metadata,
            "elapsed_seconds": time.monotonic() - started,
        },
        synthetic=synthetic,
    )
    if config.profile == OPERATIONAL_V1 and retrospective:
        write_artifacts(
            aq,
            weather,
            stations,
            replace(config, profile=RESEARCH_ENRICHED_V1),
            Path(output) / "research_enriched_v1",
            sensor_manifest,
            cache=api.cache,
            stats={"remote_requests": 0, "shared_source_snapshots": True},
            synthetic=synthetic,
        )
    return manifest


def write_artifacts(
    aq, weather, stations, config, output, sensors, cache=None, stats=None, synthetic=False
):
    started = time.monotonic()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    frame, features = construct(aq, weather, stations, config)
    frozen = freeze_spike_rule(frame)
    frame = apply_spike_rule(frame, frozen)
    availability = availability_manifest(features, config)
    leakage = validate(
        frame, aq, weather, stations, config, features, frozen, feature_availability=availability
    )
    write_json(output / "feature_availability_manifest.json", availability)
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
        "ready_for_operational_training": (
            not synthetic
            and config.profile == OPERATIONAL_V1
            and (hourly(config.end) - hourly(config.start)).days >= 90
            and len(stations) >= 2
            and bool(frame.groupby("station_id").operational_eligible.sum().ge(24).all())
        ),
        "operational_readiness_condition": availability["deployment_label"],
        "profile": config.profile,
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
            "pm25_t": "research-only hour ending at t; µg/m³; >=75% coverage",
            "pm25_latest_available": "hour ending at t-buffer; µg/m³; no forward-fill",
            "aq_window_end": "t-buffer operational; t research",
            "timestamp_phase": "native hourly interval end in UTC; station offset 0 or 30 minutes",
            "pm25_lag_Nh": "same-station value exactly t-N hours; µg/m³",
            "pm25_rolling_mean_Nh": "complete N hours ending at aq_window_end; µg/m³",
            "pm25_rolling_std_Nh": "population std ddof=0 over same full window; µg/m³",
            "trailing_30d_pXX_pm25": "30d quantile ending at aq_window_end; >=576/720 hours; µg/m³",
            "history_count_30d": "usable hours in 30d ending at aq_window_end",
            "calendar": "hour_of_day/day_of_week/month/weekend in recorded station timezone",
            "optional_pollutant": "lag buffer/buffer+1 operational; t/lag1 research; native units",
            "era5": "latest UTC analysis hour <= t; native units; retrospective publication",
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
        "operational_eligible_rows": int(frame.operational_eligible.sum()),
        "regression_eligible_rows": int(
            (frame.regression_eligible & (frame.split != "purged")).sum()
        ),
        "missing_fraction": {c: float(frame[c].isna().mean()) for c in features},
        "split_boundaries": split_boundaries(config),
        "code_git_commit": commit,
        "code_worktree_dirty": dirty,
        "runtime": {**(stats or {}), "frame_seconds": time.monotonic() - started},
        "limitations": leakage["publication_limitations"]
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
        for name in (
            "normalized_aq.parquet",
            "normalized_era5.parquet",
            "prediction_frame.parquet",
            "feature_availability_manifest.json",
        )
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
    attrition = []
    for station_id, rows in frame.groupby("station_id"):
        primary = "pm25_latest_available" if config.profile == OPERATIONAL_V1 else "pm25_t"
        eligible = rows.regression_eligible & rows.pm25_feature_complete & (rows.split != "purged")
        attrition.append(
            {
                "station_id": str(station_id),
                "expected_output_hours": len(rows),
                "latest_input_observed_slots": int(rows[primary].notna().sum()),
                "missing_latest_input_percent": float(rows[primary].isna().mean() * 100),
                "valid_pm_feature_rows": int(rows.pm25_feature_complete.sum()),
                "valid_six_hour_target_rows": int((rows.future_observation_count == 6).sum()),
                "warmup_hours_excluded_from_output": 720
                + (config.aq_availability_buffer_hours if config.profile == OPERATIONAL_V1 else 0),
                "rows_without_trailing_history": int(rows.trailing_30d_p90_pm25.isna().sum()),
                "rows_lost_to_missing_future_target": int(
                    (rows.future_observation_count < 6).sum()
                ),
                "additional_rows_lost_to_buffer": int(
                    (rows.regression_without_buffer_eligible & ~rows.regression_eligible).sum()
                ),
                "rows_recovered_by_buffer": int(
                    (~rows.regression_without_buffer_eligible & rows.regression_eligible).sum()
                ),
                "purged_rows": int(rows.split.eq("purged").sum()),
                "final_usable_operational_rows": int(eligible.sum())
                if config.profile == OPERATIONAL_V1
                else None,
                "counts_overlap_not_additive": True,
            }
        )
    write_json(output / "row_attrition.json", attrition)
    return manifest


def load_artifacts(directory):
    path = Path(directory)
    manifest = json.loads((path / "dataset_manifest.json").read_text())
    import hashlib

    for name in (
        "normalized_aq.parquet",
        "normalized_era5.parquet",
        "prediction_frame.parquet",
        "feature_availability_manifest.json",
    ):
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


def verify_real_feasibility(directory):
    """Shared fail-closed prerequisite for expensive real extraction; no network calls."""
    from prediction.frame import FrameConfig

    manifest, frame, aq, weather = load_artifacts(directory)
    config = FrameConfig(**manifest["config"])
    days = (hourly(config.end) - hourly(config.start)).total_seconds() / 86400
    if manifest["synthetic"] or config.profile != OPERATIONAL_V1 or not 14 <= days <= 31:
        raise DatasetError("Gate must be a real multi-station 2–4 week operational-profile build")
    if len(manifest["stations"]) < 2 or weather.empty:
        raise DatasetError("Gate must contain two real stations and ERA5")
    validate(
        frame,
        aq,
        weather,
        manifest["stations"],
        config,
        manifest["features"],
        manifest["targets"]["spike_next_6h"],
        require_operational=True,
        feature_availability=json.loads(
            (Path(directory) / "feature_availability_manifest.json").read_text()
        ),
    )
    research, _ = construct(
        aq, weather, manifest["stations"], replace(config, profile=RESEARCH_ENRICHED_V1)
    )
    core_weather = [f"era5_{band}" for band in ERA5_BANDS]
    for station in manifest["stations"]:
        operational = frame[frame.station_id == str(station["id"])]
        met = research[research.station_id == str(station["id"])]
        if operational.operational_eligible.sum() < 24:
            raise DatasetError(
                "Feasibility needs at least 24 complete operational rows per station"
            )
        if met[core_weather].notna().all(axis=1).mean() < 0.8:
            raise DatasetError("Feasibility needs >=80% complete ERA5 bands per station")
    return {
        "status": "pass",
        "stations": len(manifest["stations"]),
        "operational_rows": int(frame.operational_eligible.sum()),
        "availability": "conditional buffered assumption, not historical publication proof",
    }
