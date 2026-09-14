import math

import pandas as pd

from prediction.common import DatasetError, hour_grid, hour_phase, hourly


def longest_gap(series):
    missing = series.isna()
    return int(missing.groupby((~missing).cumsum()).sum().max()) if len(series) else 0


def coverage_report(aq, start, end, expected_sensors=()):
    start, end = hourly(start), hourly(end)
    rows = []
    groups = dict(tuple(aq.groupby(["station_id", "sensor_id", "pollutant", "unit"])))
    for sensor in expected_sensors:
        key = (
            str(sensor["station_id"]),
            int(sensor["sensor_id"]),
            sensor["pollutant"],
            sensor["unit"],
        )
        groups.setdefault(
            key,
            pd.DataFrame(
                {
                    "timestamp": pd.DatetimeIndex([], tz="UTC"),
                    "value": pd.Series(dtype=float),
                }
            ),
        )
    for (station, sensor, pollutant, unit), group in groups.items():
        phase = hour_phase(group.timestamp)
        grid = hour_grid(start, end, phase)
        values = group.set_index("timestamp").value.reindex(grid)
        future_count = (
            pd.concat([values.shift(-n) for n in range(1, 7)], axis=1).notna().sum(axis=1)
        )
        periods = [("all", values)] + [
            (str(month), block) for month, block in values.groupby(values.index.strftime("%Y-%m"))
        ]
        for month, block in periods:
            valid = block.dropna()
            rows.append(
                {
                    "station_id": str(station),
                    "sensor_id": int(sensor),
                    "pollutant": pollutant,
                    "unit": unit,
                    "month": month,
                    "expected_hours": len(block),
                    "hour_offset_minutes": phase,
                    "valid_hours": len(valid),
                    "missing_percent": 100 * (1 - len(valid) / len(block)),
                    "longest_gap_hours": longest_gap(block),
                    "first_valid": valid.index.min() if len(valid) else None,
                    "last_valid": valid.index.max() if len(valid) else None,
                    "valid_target_windows": int((future_count.reindex(block.index) == 6).sum()),
                    "usable_regression_rows": int(
                        ((future_count.reindex(block.index) == 6) & block.notna()).sum()
                    ),
                }
            )
    return pd.DataFrame(rows)


def select_stations(locations, coverage, count=5, min_coverage=0.8, min_months=3):
    if coverage.empty:
        raise DatasetError("No measured station coverage; selection cannot proceed")
    candidates = coverage[(coverage.month == "all") & (coverage.pollutant == "pm25")].copy()
    candidates = candidates[
        (candidates.missing_percent <= 100 * (1 - min_coverage))
        & (candidates.usable_regression_rows > 0)
    ]
    # Choose one sensor per location by measured coverage, deterministic sensor-ID tie break.
    candidates = candidates.sort_values(
        ["valid_hours", "sensor_id"], ascending=[False, True]
    ).drop_duplicates("station_id")
    selected = []
    for _, candidate in candidates.iterrows():
        monthly = coverage[
            (coverage.station_id == candidate.station_id)
            & (coverage.sensor_id == candidate.sensor_id)
            & (coverage.month != "all")
        ]
        if int((monthly.missing_percent <= 100 * (1 - min_coverage)).sum()) < min_months:
            continue
        location = next(
            location for location in locations if str(location["id"]) == candidate.station_id
        )
        selected.append(
            {
                "id": candidate.station_id,
                "name": location.get("name"),
                "latitude": location["coordinates"]["latitude"],
                "longitude": location["coordinates"]["longitude"],
                "timezone": location["timezone"],
                "pm25_sensor_id": int(candidate.sensor_id),
                "hour_offset_minutes": int(candidate.get("hour_offset_minutes", 0)),
                "instruments": location.get("instruments"),
                "provider": location.get("provider"),
                "owner": location.get("owner"),
                "licenses": location.get("licenses"),
                "sensors": location.get("sensors", []),
                "selection_reason": "Measured PM2.5 coverage "
                f"{100 - candidate.missing_percent:.2f}%; "
                f"{int(candidate.usable_regression_rows)} usable regression rows; "
                f"{len(monthly)} months inspected. Highest-coverage sensor at location.",
            }
        )
    # Coverage is a hard gate. Maximize spread only among qualifying monitors.
    if not selected:
        return []
    spread = [selected.pop(0)]
    while selected and len(spread) < count:

        def distance(station):
            return min(station_distance(station, other) for other in spread)

        chosen = max(selected, key=distance)
        chosen["selection_reason"] += (
            f" Geographic spread: {distance(chosen):.1f} km from nearest selected monitor."
        )
        spread.append(chosen)
        selected.remove(chosen)
    return spread


def station_distance(a, b):
    lat1, lat2 = math.radians(a["latitude"]), math.radians(b["latitude"])
    dlat = lat2 - lat1
    dlng = math.radians(b["longitude"] - a["longitude"])
    hav = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1, math.sqrt(hav)))
