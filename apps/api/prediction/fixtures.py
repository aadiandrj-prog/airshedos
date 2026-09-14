"""Deterministic SYNTHETIC test data, never historical NCR monitoring evidence."""

import numpy as np
import pandas as pd

from prediction.common import ERA5_BANDS, hourly
from prediction.frame import FrameConfig
from prediction.openaq import AQ_COLUMNS


def synthetic_inputs():
    config = FrameConfig(
        "2025-01-01T00:00:00Z", "2025-04-01T00:00:00Z", profile="RESEARCH_ENRICHED_V1"
    )
    times = pd.date_range(
        hourly(config.start) - pd.Timedelta(days=30),
        hourly(config.end),
        freq="h",
        inclusive="left",
    )
    aq, weather, stations = [], [], []
    for number, (lat, lng) in enumerate(((28.46, 77.03), (28.61, 77.21), (28.58, 77.36)), 1):
        station_id = f"synthetic-{number}"
        sensor = {"id": number, "parameter": {"name": "pm25", "units": "µg/m³"}}
        stations.append(
            {
                "id": station_id,
                "name": f"SYNTHETIC TEST LOCATION {number}",
                "latitude": lat,
                "longitude": lng,
                "timezone": "Asia/Kolkata",
                "pm25_sensor_id": number,
                "sensors": [sensor],
                "selection_reason": "Synthetic test location; no real monitoring evidence",
            }
        )
        hours = np.arange(len(times))
        values = 40 + number * 5 + 30 * np.sin(hours * 2 * np.pi / 24)
        values += 30 * ((hours % 53) < 4)
        values = values.astype(float)
        values[(hours + number) % 307 == 0] = np.nan
        aq.append(
            pd.DataFrame(
                {
                    "station_id": station_id,
                    "sensor_id": number,
                    "pollutant": "pm25",
                    "unit": "µg/m³",
                    "value": values,
                    "timestamp": times,
                    "period_start": times - pd.Timedelta(hours=1),
                    "coverage_percent": 100,
                    "quality": np.where(np.isnan(values), "missing", "usable"),
                    "retrieved_at": pd.Timestamp("2026-01-01T00:00:00Z"),
                    "available_at": pd.NaT,
                },
                columns=AQ_COLUMNS,
            )
        )
        met = pd.DataFrame({"station_id": station_id, "timestamp": times})
        for band, value in zip(ERA5_BANDS, (290, 280, 100000, 0.001, 3, 4), strict=True):
            met[band] = value
        met["wind_speed_mps"] = 5.0
        met["wind_from_degrees"] = 216.86989764584402
        met["available_at"] = pd.NaT
        met["retrieved_at"] = pd.Timestamp("2026-01-01T00:00:00Z")
        met["collection"] = "SYNTHETIC ERA5-shaped fixture; no remote observations"
        weather.append(met)
    return pd.concat(aq, ignore_index=True), pd.concat(weather, ignore_index=True), stations, config
