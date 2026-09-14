"""Hourly, station-isolated features and six-hour targets. No interpolation or training."""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from prediction.availability import DEFAULT_AQ_BUFFER_HOURS, OPERATIONAL_V1, RESEARCH_ENRICHED_V1
from prediction.common import ERA5_BANDS, DatasetError, hour_grid, hour_phase, hourly

LAGS = (1, 2, 3, 6, 12, 24)
ROLLS = (3, 6, 12, 24)
TARGETS = ("future_max_pm25_6h", "future_mean_pm25_6h", "spike_next_6h")


@dataclass(frozen=True)
class FrameConfig:
    start: str
    end: str
    history_days: int = 30
    history_min_hours: int = 576
    future_min_hours: int = 6
    profile: str = OPERATIONAL_V1
    aq_availability_buffer_hours: int = DEFAULT_AQ_BUFFER_HOURS

    def __post_init__(self):
        if self.profile not in {OPERATIONAL_V1, RESEARCH_ENRICHED_V1}:
            raise DatasetError("Unknown feature profile")
        if (
            isinstance(self.aq_availability_buffer_hours, bool)
            or not isinstance(self.aq_availability_buffer_hours, int)
            or not 1 <= self.aq_availability_buffer_hours <= 168
        ):
            raise DatasetError("AQ availability buffer must be an integer from 1 to 168 hours")
        if hourly(self.end) <= hourly(self.start):
            raise DatasetError("Invalid dataset date range")
        if self.history_days != 30 or self.history_min_hours < 576 or self.history_min_hours > 720:
            raise DatasetError("30-day reference requires at least 576 of 720 hours")
        if self.future_min_hours != 6:
            raise DatasetError("This version requires all six future hours")

    def to_dict(self):
        return asdict(self)


def split_boundaries(config):
    start, end = hourly(config.start), hourly(config.end)

    def boundary(fraction):
        candidate = start + (end - start) * fraction
        if end - start >= pd.Timedelta(days=180):
            lower = candidate.normalize().replace(day=1)
            upper = lower + pd.offsets.MonthBegin(1)
            return min((lower, upper), key=lambda t: abs(t - candidate))
        return candidate.floor("h")

    train_end, validation_end = boundary(0.70), boundary(0.85)
    if min(train_end - start, validation_end - train_end, end - validation_end) < pd.Timedelta(
        hours=24
    ):
        raise DatasetError("Split periods must each span at least 24 hours")
    return {
        "train_start": start.isoformat(),
        "train_end_exclusive": train_end.isoformat(),
        "validation_start": train_end.isoformat(),
        "validation_end_exclusive": validation_end.isoformat(),
        "test_start": validation_end.isoformat(),
        "test_end_exclusive": end.isoformat(),
        "purge_hours": 6,
        "method": "aligned_chronological_no_shuffle",
    }


def assign_splits(frame, boundaries):
    result = pd.Series("purged", index=frame.index, dtype="string")
    for name in ("train", "validation", "test"):
        start = hourly(boundaries[f"{name}_start"])
        end = hourly(boundaries[f"{name}_end_exclusive"])
        # Last target observation must precede the next period, not merely row time t.
        mask = (frame.timestamp >= start) & (frame.timestamp + pd.Timedelta(hours=6) < end)
        result.loc[mask] = name
    return result


def construct(aq, weather, stations, config):
    start, end = hourly(config.start), hourly(config.end)
    operational = config.profile == OPERATIONAL_V1
    buffer = config.aq_availability_buffer_hours if operational else 0
    warmup = start - pd.Timedelta(days=30, hours=buffer)
    frames, features = [], []
    for station in sorted(stations, key=lambda s: str(s["id"])):
        station_id = str(station["id"])
        observations = aq[aq.station_id.astype(str) == station_id]
        if observations.duplicated(["pollutant", "timestamp"]).any():
            raise DatasetError(
                "Multiple sensors per pollutant/hour; select explicitly before constructing frame"
            )
        pm = observations[observations.pollutant == "pm25"]
        if pm.empty or set(pm.unit) != {"µg/m³"}:
            raise DatasetError("Station PM2.5 must have compatible µg/m³ units")
        phase = hour_phase(pm.timestamp)
        if phase != station.get("hour_offset_minutes", 0):
            raise DatasetError("Station hourly phase differs from measured source periods")
        grid = hour_grid(warmup, end, phase)
        observed_pm = pm.set_index("timestamp").value.reindex(grid).astype(float)
        inputs = observations.copy()
        if operational:
            revised = inputs.quality.astype(str).str.contains("revision", case=False)
            if "revision_detected" in inputs:
                revised |= inputs.revision_detected.fillna(False).astype(bool)
            if "available_at" in inputs:
                known_release = pd.to_datetime(inputs.available_at, utc=True)
                revised |= known_release > (inputs.timestamp + pd.Timedelta(hours=buffer))
            inputs.loc[revised, "value"] = np.nan
        pm_input = inputs[inputs.pollutant == "pm25"].set_index("timestamp").value.reindex(grid)
        pm = pm_input.shift(buffer).astype(float)
        part = pd.DataFrame({"station_id": station_id, "timestamp": grid}, index=grid)
        primary = "pm25_latest_available" if operational else "pm25_t"
        part[primary] = pm
        local = grid.tz_convert(station["timezone"])
        for name, values in {
            "hour_of_day": local.hour,
            "day_of_week": local.dayofweek,
            "month": local.month,
            "weekend": local.dayofweek >= 5,
        }.items():
            part[name] = values
        for lag in LAGS:
            if not operational or lag > buffer:
                part[f"pm25_lag_{lag}h"] = pm_input.shift(lag)
        if operational:
            # Keep useful older history even when the conservative buffer exceeds 24 hours.
            for offset in (1, 2, 3, 6, 12, 24):
                lag = buffer + offset
                part[f"pm25_lag_{lag}h"] = pm_input.shift(lag)
        for window in (3, 6, 12) if operational else ROLLS:
            part[f"pm25_rolling_mean_{window}h"] = pm.rolling(window, min_periods=window).mean()
        for window in (6,) if operational else (6, 24):
            part[f"pm25_rolling_std_{window}h"] = pm.rolling(window, min_periods=window).std(ddof=0)
        part["history_count_30d"] = pm.rolling("30D", closed="right").count()
        history_valid = (part.history_count_30d >= config.history_min_hours) & (
            grid >= warmup + pd.Timedelta(days=30, hours=buffer)
        )
        for q in (0.85, 0.90, 0.95):
            part[f"trailing_30d_p{round(q * 100)}_pm25"] = (
                pm.rolling("30D", closed="right", min_periods=config.history_min_hours)
                .quantile(q)
                .where(history_valid)
            )
        for pollutant, group in inputs[inputs.pollutant != "pm25"].groupby("pollutant"):
            if len(set(group.unit)) != 1:
                raise DatasetError("Unit changes within an optional sensor")
            unit = group.unit.iloc[0]
            suffix = {"µg/m³": "ug_m3", "ppb": "ppb", "ppm": "ppm"}.get(unit)
            if suffix is None:
                raise DatasetError("Unsupported optional pollutant unit")
            column = f"{pollutant}_{suffix}"
            if hour_phase(group.timestamp) != phase:
                raise DatasetError("Optional sensor hourly phase differs from PM2.5")
            values = group.set_index("timestamp").value.reindex(grid)
            if operational:
                part[f"{column}_lag_{buffer}h"] = values.shift(buffer)
                part[f"{column}_lag_{buffer + 1}h"] = values.shift(buffer + 1)
            else:
                part[f"{column}_t"] = values
                part[f"{column}_lag_1h"] = values.shift(1)
        met = (
            weather[weather.station_id.astype(str) == station_id]
            if len(weather) and not operational
            else pd.DataFrame()
        )
        if len(met):
            if met.duplicated("timestamp").any():
                raise DatasetError("Duplicate meteorology hour")
            met = met.set_index("timestamp").reindex(grid.floor("h"))
            met.index = grid
            for band in [*ERA5_BANDS, "wind_speed_mps", "wind_from_degrees"]:
                part[f"era5_{band}"] = met[band]
        elif not operational:
            for band in [*ERA5_BANDS, "wind_speed_mps", "wind_from_degrees"]:
                part[f"era5_{band}"] = np.nan
        feature_names = [c for c in part if c not in {"station_id", "timestamp"}]
        features.extend(c for c in feature_names if c not in features)
        future = pd.concat([observed_pm.shift(-h) for h in range(1, 7)], axis=1)
        part["future_observation_count"] = future.notna().sum(axis=1)
        valid = part.future_observation_count == config.future_min_hours
        part["future_max_pm25_6h"] = future.max(axis=1).where(valid)
        part["future_mean_pm25_6h"] = future.mean(axis=1).where(valid)
        part["regression_eligible"] = valid & part[primary].notna()
        # These distinguish observation-time correctness from as-of availability proof.
        part["feature_observation_end"] = grid - pd.Timedelta(hours=buffer)
        part["aq_feature_cutoff"] = grid - pd.Timedelta(hours=buffer)
        part["feature_profile"] = config.profile
        part["aq_availability_buffer_hours"] = buffer
        part["feature_complete"] = part[feature_names].notna().all(axis=1)
        part["pm25_feature_complete"] = (
            part[[c for c in feature_names if c.startswith("pm25_")]].notna().all(axis=1)
        )
        part["regression_without_buffer_eligible"] = valid & observed_pm.notna()
        part["target_window_start"] = grid + pd.Timedelta(hours=1)
        part["target_window_end"] = grid + pd.Timedelta(hours=6)
        part["publication_availability_verified"] = False
        frames.append(part[part.timestamp >= start].reset_index(drop=True))
    if not frames:
        raise DatasetError("No selected station frame")
    result = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["timestamp", "station_id"])
        .reset_index(drop=True)
    )
    result["split"] = assign_splits(result, split_boundaries(config))
    result["operational_eligible"] = (
        result.regression_eligible & result.pm25_feature_complete & result.split.ne("purged")
        if operational
        else False
    )
    return result, features


def spike_labels(frame, percentile, relative_increase):
    reference = frame[f"trailing_30d_p{percentile}_pm25"]
    current = frame["pm25_latest_available"] if "pm25_latest_available" in frame else frame.pm25_t
    valid = frame.regression_eligible & reference.notna()
    label = (
        (frame.future_max_pm25_6h >= reference)
        & (frame.future_max_pm25_6h >= current * (1 + relative_increase))
        & (frame.future_max_pm25_6h > current)
    )  # All-zero persistence is not worsening.
    return label.astype("Int64").where(valid)


def freeze_spike_rule(frame):
    train = frame[frame.split == "train"]
    if "feature_profile" in frame and frame.feature_profile.eq(OPERATIONAL_V1).all():
        train = train[train.operational_eligible]
    candidates = []
    for percentile in (85, 90, 95):
        for increase in (0.20, 0.25, 0.30):
            labels = spike_labels(train, percentile, increase).dropna()
            candidates.append(
                {
                    "percentile": percentile,
                    "relative_increase": increase,
                    "training_n": len(labels),
                    "training_positive_rate": float(labels.mean()) if len(labels) else None,
                }
            )
    eligible = [
        c
        for c in candidates
        if c["training_n"] >= 100 and 0.05 <= c["training_positive_rate"] <= 0.35
    ]
    # Predeclared operational preference, not validation/test metric optimization.
    selected = (
        min(
            eligible,
            key=lambda c: (
                abs(c["training_positive_rate"] - 0.20),
                abs(c["percentile"] - 90),
                abs(c["relative_increase"] - 0.25),
            ),
        )
        if eligible
        else None
    )
    return {
        "selection_data": "training_rows_only",
        "candidates": candidates,
        "selected": selected,
        "status": "frozen" if selected else "insufficient_training_labels_or_extreme_imbalance",
        "predeclared_policy": (
            "At least 100 training labels; prevalence 5–35%; closest to 20%; "
            "ties prefer p90 and 25% increase. Never choose using "
            "validation/test."
        ),
    }


def apply_spike_rule(frame, frozen):
    result = frame.copy()
    selected = frozen.get("selected")
    result["spike_next_6h"] = (
        spike_labels(result, selected["percentile"], selected["relative_increase"])
        if selected
        else pd.Series(pd.NA, index=result.index, dtype="Int64")
    )
    return result


def fire_features(events, station_id, times):
    """Optional exact-event contract; daily rasters cannot be silently converted to events."""
    output = []
    for t in times:
        t = hourly(t)
        source = events[
            (events.station_id.astype(str) == str(station_id))
            & (events.observed_at > t - pd.Timedelta(hours=24))
            & (events.observed_at <= t)
            & events.available_at.notna()
            & (events.available_at <= t)
        ]
        output.append(
            {
                "station_id": str(station_id),
                "timestamp": t,
                **{
                    f"fire_count_{r}km_prev_24h": int((source.distance_km <= r).sum())
                    for r in (25, 50, 100)
                },
            }
        )
    return pd.DataFrame(output)
