"""Strict offline data contract and reproducible local cache. No runtime imports."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

VERSION = "prediction_dataset_v1"
ERA5_COLLECTION = "ECMWF/ERA5_LAND/HOURLY"
ERA5_BANDS = {
    "temperature_2m": "K",
    "dewpoint_temperature_2m": "K",
    "surface_pressure": "Pa",
    "total_precipitation_hourly": "m",
    "u_component_of_wind_10m": "m/s",
    "v_component_of_wind_10m": "m/s",
}
POLLUTANTS = ("pm25", "pm10", "no2", "co", "o3", "so2")
NCR_BBOX = (76.65, 28.25, 77.65, 28.9)  # Core NCR study box, not a jurisdiction polygon.


class DatasetError(ValueError):
    pass


def utc(value):
    result = pd.Timestamp(value)
    if pd.isna(result) or result.tzinfo is None:
        raise DatasetError("Timestamp must be timezone-aware")
    return result.tz_convert("UTC")


def hourly(value):
    value = utc(value)
    if value != value.floor("h"):
        raise DatasetError("Expected exact UTC hour boundary; never silently round measurements")
    return value


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, allow_nan=False).encode()
    ).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, default=str, ensure_ascii=False, allow_nan=False) + "\n"
    )
    temporary.replace(path)


class RawCache:
    def __init__(self, root):
        self.root = Path(root)
        self.hits = 0
        self.misses = 0
        self.references = {}

    def path(self, source, query):
        return self.root / source / f"{digest({'version': VERSION, 'query': query})}.json"

    def get(self, source, query):
        path = self.path(source, query)
        if not path.exists():
            self.misses += 1
            return None
        cached = json.loads(path.read_text())
        if (
            cached["source"] != source
            or cached["query"] != query
            or digest(cached["data"]) != cached["sha256"]
        ):
            raise DatasetError("Raw cache integrity failure; remove the affected cache entry")
        self.hits += 1
        self.references[str(path)] = {
            k: cached[k] for k in ("source", "query", "retrieved_at", "sha256")
        }
        return cached

    def put(self, source, query, data):
        value = {
            "source": source,
            "query": query,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "sha256": digest(data),
            "data": data,
        }
        write_json(self.path(source, query), value)
        self.references[str(self.path(source, query))] = {
            k: value[k] for k in ("source", "query", "retrieved_at", "sha256")
        }
        return value


def chunks(start, end, days=28):
    start, end = hourly(start), hourly(end)
    if end <= start:
        raise DatasetError("End must be later than start")
    while start < end:
        stop = min(end, start + pd.Timedelta(days=days))
        yield start, stop
        start = stop
