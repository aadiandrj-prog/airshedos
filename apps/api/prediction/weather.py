"""Batched regional reanalysis extraction, explicitly not available at issue hour t."""

import logging
import math
import time

import ee
import pandas as pd

from prediction.common import ERA5_BANDS, ERA5_COLLECTION, DatasetError, chunks, hourly, utc

logger = logging.getLogger(__name__)


def wind(u, v):
    speed = math.hypot(u, v)
    return speed, (math.degrees(math.atan2(-u, -v)) % 360 if speed > 0 else None)


def normalize_era5(rows, retrieved_at):
    result = []
    for raw in rows:
        try:
            timestamp = hourly(pd.Timestamp(raw["time_ms"], unit="ms", tz="UTC"))
            row = {
                "station_id": str(raw["station_id"]),
                "timestamp": timestamp,
                "retrieved_at": utc(retrieved_at),
                "available_at": pd.NaT,
                "collection": ERA5_COLLECTION,
                "quality_notes": "",
            }
            for band in ERA5_BANDS:
                value = raw.get(band)
                row[band] = (
                    float(value) if value is not None and math.isfinite(float(value)) else None
                )
            if (
                row["total_precipitation_hourly"] is not None
                and row["total_precipitation_hourly"] < 0
            ):
                row["total_precipitation_hourly"] = None
                row["quality_notes"] = (
                    "negative_hourly_precipitation_packing_artifact; raw retained in cache"
                )
            u, v = row["u_component_of_wind_10m"], row["v_component_of_wind_10m"]
            row["wind_speed_mps"], row["wind_from_degrees"] = (
                wind(u, v) if u is not None and v is not None else (None, None)
            )
            result.append(row)
        except (KeyError, TypeError, ValueError):
            raise DatasetError("Malformed ERA5 hourly feature") from None
    frame = pd.DataFrame(result)
    if len(frame) and frame.duplicated(["station_id", "timestamp"]).any():
        raise DatasetError("Duplicate ERA5 station-hour")
    return frame


class ERA5:
    def __init__(self, project, cache, query=None):
        self.project, self.cache, self.query = project, cache, query
        self.initialized = False
        self.requests = 0

    def remote(self, stations, start, end):
        if not self.initialized:
            if not self.project:
                raise DatasetError("Earth Engine project is not configured")
            ee.Initialize(project=self.project)
            ee.data.setDeadline(60000)
            ee.data.setMaxRetries(0)
            self.initialized = True
        points = ee.FeatureCollection(
            [
                ee.Feature(
                    ee.Geometry.Point([s["longitude"], s["latitude"]]), {"station_id": str(s["id"])}
                )
                for s in stations
            ]
        )
        images = ee.ImageCollection(ERA5_COLLECTION).filterDate(start, end).select(list(ERA5_BANDS))

        def extract(raw):
            image = ee.Image(raw)
            return image.reduceRegions(
                collection=points, reducer=ee.Reducer.first(), scale=11132
            ).map(lambda f: f.set("time_ms", image.get("system:time_start")).setGeometry(None))

        # One RPC for all stations and up to seven days, never one RPC per final row.
        table = ee.FeatureCollection(images.toList(7 * 24).map(extract)).flatten()
        return [f["properties"] for f in table.getInfo()["features"]]

    def extract(self, stations, start, end):
        frames = []
        for begin, stop in chunks(start, end, days=7):
            query = {
                "collection": ERA5_COLLECTION,
                "bands": list(ERA5_BANDS),
                "scale_m": 11132,
                "stations": [
                    {"id": str(s["id"]), "latitude": s["latitude"], "longitude": s["longitude"]}
                    for s in stations
                ],
                "start": begin.isoformat(),
                "end": stop.isoformat(),
            }
            started = time.monotonic()
            cached = self.cache.get("era5", query)
            hit = cached is not None
            if cached is None:
                try:
                    self.requests += 1
                    rows = (self.query or self.remote)(stations, query["start"], query["end"])
                except Exception as exc:
                    if isinstance(exc, DatasetError):
                        raise
                    raise DatasetError(
                        "Earth Engine extraction failed; cached chunks remain resumable. "
                        "Check ADC/project access."
                    ) from None
                cached = self.cache.put("era5", query, rows)
            frame = normalize_era5(cached["data"], cached["retrieved_at"])
            if frame.empty:
                raise DatasetError(
                    "ERA5 returned no rows for a requested chunk; do not substitute weather"
                )
            expected_ids = {str(s["id"]) for s in stations}
            if (
                not set(frame.station_id) <= expected_ids
                or not frame.timestamp.between(begin, stop, inclusive="left").all()
            ):
                raise DatasetError("ERA5 returned out-of-query station/hour")
            frames.append(frame)
            logger.info(
                "source=era5 stations=%s chunk=%s/%s rows=%s cache_hit=%s elapsed=%.2f",
                len(stations),
                begin,
                stop,
                len(frame),
                hit,
                time.monotonic() - started,
            )
        return pd.concat(frames, ignore_index=True)
