"""Official OpenAQ v3 /hours, bounded pagination, cached chunks and safe logs."""

import logging
import math
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

from prediction.common import NCR_BBOX, DatasetError, chunks, digest, hourly, utc

logger = logging.getLogger(__name__)
PM_UNITS = {"µg/m³", "μg/m³", "ug/m3", "µg/m3", "μg/m3"}
GAS_UNITS = {"ppb", "ppm", *PM_UNITS}
AQ_COLUMNS = [
    "station_id",
    "sensor_id",
    "pollutant",
    "unit",
    "value",
    "timestamp",
    "period_start",
    "coverage_percent",
    "quality",
    "retrieved_at",
    "available_at",
]


class OpenAQ:
    def __init__(
        self,
        key,
        cache,
        client=None,
        sleep=time.sleep,
        clock=time.monotonic,
        min_interval_seconds=2.0,
        max_requests=1800,
    ):
        self.key, self.cache = key, cache
        self.client = client or httpx.Client(timeout=45, follow_redirects=False)
        self.sleep, self.clock = sleep, clock
        self.interval, self.max_requests = min_interval_seconds, max_requests
        self.requests = 0
        self.last_request = None

    def close(self):
        self.client.close()

    def page(self, path, params):
        query = {"path": path, "params": params}
        cached = self.cache.get("openaq", query)
        if cached:
            return cached
        if not self.key:
            raise DatasetError("OPENAQ_API_KEY is not configured; live extraction is blocked")
        for attempt in range(3):
            if self.requests >= self.max_requests:
                raise DatasetError("OpenAQ request budget reached; cached progress is resumable")
            if self.last_request is not None:
                self.sleep(max(0, self.interval - (self.clock() - self.last_request)))
            self.last_request = self.clock()
            self.requests += 1
            try:
                response = self.client.get(
                    f"https://api.openaq.org/v3/{path}",
                    params=params,
                    headers={"X-API-Key": self.key},
                )
            except httpx.HTTPError:
                if attempt == 2:
                    raise DatasetError("OpenAQ transport failed after bounded retries") from None
                self.sleep(2**attempt)
                continue
            if response.status_code in {401, 403}:
                raise DatasetError("OpenAQ authentication/permission failed; check the backend key")
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 2:
                    raise DatasetError(
                        f"OpenAQ HTTP {response.status_code}; retry budget exhausted"
                    )
                raw = response.headers.get("Retry-After", "")
                try:
                    delay = float(raw)
                except ValueError:
                    try:
                        delay = (parsedate_to_datetime(raw) - datetime.now(UTC)).total_seconds()
                    except (ValueError, TypeError):
                        delay = 60 if response.status_code == 429 else 2**attempt
                if delay > 60:
                    raise DatasetError(
                        "OpenAQ requested a long rate-limit pause; resume later from cache"
                    )
                self.sleep(max(1, delay))
                continue
            if response.status_code != 200:
                raise DatasetError(f"OpenAQ HTTP {response.status_code}; no raw response logged")
            if len(response.content) > 10_000_000:
                raise DatasetError("OpenAQ response exceeded the bounded page size")
            try:
                data = response.json()
                if not isinstance(data.get("results"), list):
                    raise ValueError
            except (ValueError, AttributeError):
                raise DatasetError("Malformed OpenAQ response") from None
            return self.cache.put("openaq", query, data)
        raise DatasetError("OpenAQ request failed")

    def pages(self, path, params=None, limit=1000, max_pages=100):
        seen = set()
        for page in range(1, max_pages + 1):
            item = self.page(path, {**(params or {}), "limit": limit, "page": page})
            rows = item["data"]["results"]
            if rows:
                signature = digest(rows)
                if signature in seen:
                    raise DatasetError(
                        "OpenAQ repeated a page; refusing a truncated/duplicated extraction"
                    )
                seen.add(signature)
            yield rows, item["retrieved_at"]
            if len(rows) < limit:
                return
            # meta.found can be '>1000'. Never treat that string as a definitive total.
        raise DatasetError("OpenAQ pagination cap reached; refusing silent truncation")

    def locations(self):
        params = {
            "iso": "IN",
            "bbox": ",".join(map(str, NCR_BBOX)),
            "monitor": "true",
            "mobile": "false",
            "order_by": "id",
            "sort_order": "asc",
        }
        results = [row for rows, _ in self.pages("locations", params) for row in rows]
        selected = [
            row
            for row in results
            if row.get("isMonitor") is True
            and row.get("isMobile") is False
            and any(s.get("parameter", {}).get("name") == "pm25" for s in row.get("sensors", []))
        ]

        for row in selected:
            try:
                lat = float(row["coordinates"]["latitude"])
                lng = float(row["coordinates"]["longitude"])
                ZoneInfo(row["timezone"])
                if not (NCR_BBOX[0] <= lng <= NCR_BBOX[2] and NCR_BBOX[1] <= lat <= NCR_BBOX[3]):
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                raise DatasetError(
                    "Invalid station coordinates/timezone or outside NCR study box"
                ) from None
        return selected

    def sensor(self, sensor_id):
        rows = self.page(f"sensors/{int(sensor_id)}", {})["data"]["results"]
        if len(rows) != 1:
            raise DatasetError("Expected one sensor metadata record")
        return rows[0]

    def hours(self, station_id, sensor, start, end):
        frames = []
        for begin, stop in chunks(start, end):
            started = self.clock()
            hit_count = self.cache.hits
            rows = []
            params = {"datetime_from": begin.isoformat(), "datetime_to": stop.isoformat()}
            for payload, retrieved in self.pages(f"sensors/{int(sensor['id'])}/hours", params):
                rows.extend(normalize_hours(payload, station_id, sensor, retrieved))
            frame = pd.DataFrame(rows, columns=AQ_COLUMNS)
            if len(frame):
                frame = frame[(frame.timestamp >= begin) & (frame.timestamp < stop)]
            frames.append(frame)
            logger.info(
                "source=openaq station=%s sensor=%s chunk=%s/%s rows=%s cache_hits=%s elapsed=%.2f",
                station_id,
                sensor["id"],
                begin,
                stop,
                len(frame),
                self.cache.hits - hit_count,
                self.clock() - started,
            )
        return deduplicate(pd.concat(frames, ignore_index=True))


def normalize_hours(rows, station_id, sensor, retrieved_at):
    output = []
    expected = sensor["parameter"]
    for row in rows:
        try:
            parameter, period = row["parameter"], row["period"]
            if parameter["name"] != expected["name"] or parameter["units"] != expected["units"]:
                raise DatasetError("Pollutant/unit changed within the selected sensor")
            pollutant, unit = parameter["name"], parameter["units"]
            accepted = PM_UNITS if pollutant in {"pm25", "pm10"} else GAS_UNITS
            if unit not in accepted:
                raise DatasetError(f"Unsupported {pollutant} unit; no silent conversion")
            unit = "µg/m³" if unit in PM_UNITS else unit
            start, end = utc(period["datetimeFrom"]["utc"]), hourly(period["datetimeTo"]["utc"])
            if end - start != pd.Timedelta(hours=1):
                raise DatasetError("OpenAQ record does not describe exactly one hour")
            raw = row["value"]
            value = float(raw) if raw is not None and not isinstance(raw, bool) else None
            coverage = (row.get("coverage") or {}).get("percentCoverage")
            valid = (
                value is not None
                and math.isfinite(value)
                and value >= 0
                and isinstance(coverage, (float, int))
                and 75 <= coverage <= 100
            )
            output.append(
                {
                    "station_id": str(station_id),
                    "sensor_id": int(sensor["id"]),
                    "pollutant": pollutant,
                    "unit": unit,
                    "value": value if valid else None,
                    "timestamp": end,
                    "period_start": start,
                    "coverage_percent": coverage,
                    "quality": "usable" if valid else "missing_negative_nonfinite_or_low_coverage",
                    "retrieved_at": utc(retrieved_at),
                    # API aggregation timestamps are not historical publication timestamps.
                    "available_at": pd.NaT,
                }
            )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, DatasetError):
                raise
            raise DatasetError("Malformed OpenAQ hourly record") from None
    return output


def deduplicate(frame):
    if frame.empty:
        return frame
    keys = ["station_id", "sensor_id", "timestamp"]
    for _, group in frame[frame.duplicated(keys, keep=False)].groupby(keys, dropna=False):
        if (
            len(
                group[
                    ["value", "unit", "pollutant", "quality", "coverage_percent", "period_start"]
                ].drop_duplicates()
            )
            > 1
        ):
            raise DatasetError("Conflicting duplicate sensor-hour values; do not average revisions")
    return frame.sort_values([*keys, "retrieved_at"]).drop_duplicates(keys).reset_index(drop=True)
