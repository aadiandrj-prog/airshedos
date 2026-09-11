import asyncio
import csv
import io
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import quote

from app.environment.geo import bounding_boxes, haversine_km
from app.environment.http import ProviderHTTP
from app.environment.models import (
    AirQualityIndex,
    AirQualityObservation,
    EnvironmentalProvenance,
    FireObservation,
    Measurement,
    MeteorologicalObservation,
    PollutantMeasurement,
)

AQ_DOC = "https://developers.google.com/maps/documentation/air-quality/current-conditions"
WEATHER_DOC = "https://developers.google.com/maps/documentation/weather/current-conditions"
FIRMS_DOC = "https://firms.modaps.eosdis.nasa.gov/api/area/"


class AirQualityProvider(Protocol):
    name: str
    configured: bool

    async def fetch(self, lat: float, lng: float) -> AirQualityObservation | None: ...


class WeatherProvider(Protocol):
    name: str
    configured: bool

    async def fetch(self, lat: float, lng: float) -> MeteorologicalObservation | None: ...


class FireProvider(Protocol):
    name: str
    configured: bool

    async def fetch(self, lat: float, lng: float) -> list[FireObservation]: ...


def provenance(source: str, method: str, doc: str, note: str) -> EnvironmentalProvenance:
    return EnvironmentalProvenance(
        source_id=source, method=method, documentation_url=doc, note=note
    )


def measurement(obj: dict | None, value: str = "value", unit: str = "unit") -> Measurement | None:
    if obj is None or obj == {}:
        return None
    # A missing concentration is different from zero. Incomplete pairs stay unavailable.
    if not isinstance(obj, dict):
        raise ValueError("Invalid measurement")
    if obj.get(value) is None or not obj.get(unit):
        return None
    return Measurement(value=obj[value], unit=obj[unit])


class GoogleAirQualityProvider:
    name = "google_air_quality"

    def __init__(self, http: ProviderHTTP, key: str):
        self.http, self._key, self.configured = http, key, bool(key)

    async def fetch(self, lat: float, lng: float) -> AirQualityObservation | None:
        response = await self.http.request(
            "POST",
            "https://airquality.googleapis.com/v1/currentConditions:lookup",
            headers={"X-Goog-Api-Key": self._key},
            json={
                "location": {"latitude": lat, "longitude": lng},
                "universalAqi": True,
                "extraComputations": ["LOCAL_AQI", "POLLUTANT_CONCENTRATION"],
                "languageCode": "en",
            },
        )
        raw = response.json()
        if not isinstance(raw, dict):
            raise ValueError("Expected object")
        if not raw.get("indexes") and not raw.get("pollutants"):
            return None
        return AirQualityObservation(
            latitude=lat,
            longitude=lng,
            observed_at=raw["dateTime"],
            retrieved_at=datetime.now(UTC),
            region_code=raw.get("regionCode"),
            indexes=[
                AirQualityIndex(
                    code=i["code"],
                    display_name=i.get("displayName"),
                    value=i.get("aqi"),
                    category=i.get("category"),
                    dominant_pollutant=i.get("dominantPollutant"),
                )
                for i in raw.get("indexes", [])
            ],
            pollutants=[
                PollutantMeasurement(
                    code=p["code"],
                    name=p.get("displayName"),
                    full_name=p.get("fullName"),
                    concentration=measurement(p.get("concentration"), unit="units"),
                )
                for p in raw.get("pollutants", [])
            ],
            provenance=provenance(
                self.name,
                "Google currentConditions lookup",
                AQ_DOC,
                "Provider estimates; not a new regulatory monitoring station. "
                "Index scales and source units are preserved.",
            ),
        )


class GoogleWeatherProvider:
    name = "google_weather"

    def __init__(self, http: ProviderHTTP, key: str):
        self.http, self._key, self.configured = http, key, bool(key)

    async def fetch(self, lat: float, lng: float) -> MeteorologicalObservation | None:
        response = await self.http.request(
            "GET",
            "https://weather.googleapis.com/v1/currentConditions:lookup",
            headers={"X-Goog-Api-Key": self._key},
            params={"location.latitude": lat, "location.longitude": lng, "unitsSystem": "METRIC"},
        )
        raw = response.json()
        if not isinstance(raw, dict):
            raise ValueError("Expected object")
        if not any(
            raw.get(k) is not None
            for k in (
                "temperature",
                "relativeHumidity",
                "wind",
                "airPressure",
                "precipitation",
                "cloudCover",
            )
        ):
            return None
        wind, precip, pressure = (
            raw.get("wind") or {},
            raw.get("precipitation") or {},
            raw.get("airPressure") or {},
        )
        direction = wind.get("direction") or {}
        degrees = direction.get("degrees")
        if degrees is not None and not 0 <= float(degrees) <= 360:
            raise ValueError("Invalid direction")
        return MeteorologicalObservation(
            latitude=lat,
            longitude=lng,
            observed_at=raw["currentTime"],
            retrieved_at=datetime.now(UTC),
            temperature=measurement(raw.get("temperature"), value="degrees"),
            relative_humidity_percent=raw.get("relativeHumidity"),
            wind_speed=measurement(wind.get("speed")),
            wind_from_degrees=float(degrees) % 360 if degrees is not None else None,
            wind_cardinal=direction.get("cardinal"),
            sea_level_pressure=Measurement(
                value=pressure["meanSeaLevelMillibars"], unit="MILLIBARS"
            )
            if pressure.get("meanSeaLevelMillibars") is not None
            else None,
            precipitation_probability_percent=(precip.get("probability") or {}).get("percent"),
            precipitation_qpf=measurement(precip.get("qpf"), value="quantity"),
            cloud_cover_percent=raw.get("cloudCover"),
            provenance=provenance(
                self.name,
                "Google currentConditions lookup",
                WEATHER_DOC,
                "Wind degrees indicate origin, clockwise from north; 360 is normalized to 0. "
                "QPF is provider precipitation estimate.",
            ),
        )


class NasaFirmsProvider:
    name = "nasa_firms"
    dataset = "VIIRS_SNPP_NRT"
    window_days = 2

    def __init__(self, http: ProviderHTTP, key: str, radius_km: float):
        self.http, self._key, self.configured, self.radius_km = http, key, bool(key), radius_km

    async def fetch(self, lat: float, lng: float) -> list[FireObservation]:
        async def get_box(box):
            coords = ",".join(f"{c:.6f}" for c in box)
            response = await self.http.request(
                "GET",
                f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{quote(self._key, safe='')}/"
                f"{self.dataset}/{coords}/{self.window_days}",
            )
            return self.normalize(response.text, lat, lng, datetime.now(UTC))

        groups = await asyncio.gather(
            *(get_box(box) for box in bounding_boxes(lat, lng, self.radius_km))
        )
        unique = {fire.source_id: fire for group in groups for fire in group}
        return sorted(unique.values(), key=lambda f: f.distance_from_query_km)

    def normalize(
        self, text: str, lat: float, lng: float, retrieved_at: datetime
    ) -> list[FireObservation]:
        reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
        required = {"latitude", "longitude", "acq_date", "acq_time"}
        if not required.issubset(reader.fieldnames or []):
            # HTTP 200 with a key/error message is not an empty successful fire query.
            raise ValueError("Invalid FIRMS CSV header")
        fires = []
        for row in reader:
            fire_lat, fire_lng = float(row["latitude"]), float(row["longitude"])
            if not -90 <= fire_lat <= 90 or not -180 <= fire_lng <= 180:
                raise ValueError("Invalid fire location")
            distance = haversine_km(lat, lng, fire_lat, fire_lng)
            if distance > self.radius_km:
                continue
            observed = datetime.strptime(
                row["acq_date"] + row["acq_time"].zfill(4), "%Y-%m-%d%H%M"
            ).replace(tzinfo=UTC)
            source_id = (
                f"{self.dataset}:{row.get('satellite', '')}:{observed.isoformat()}:"
                f"{fire_lat}:{fire_lng}"
            )
            fires.append(
                FireObservation(
                    latitude=fire_lat,
                    longitude=fire_lng,
                    observed_at=observed,
                    retrieved_at=retrieved_at,
                    source_id=source_id,
                    confidence=row.get("confidence") or None,
                    satellite=row.get("satellite") or None,
                    instrument=row.get("instrument") or None,
                    brightness=Measurement(value=row["bright_ti4"], unit="KELVIN")
                    if row.get("bright_ti4")
                    else None,
                    fire_radiative_power=Measurement(value=row["frp"], unit="MEGAWATTS")
                    if row.get("frp")
                    else None,
                    distance_from_query_km=round(distance, 3),
                    provenance=provenance(
                        source_id,
                        "VIIRS S-NPP NRT; bounding box then radius filter",
                        FIRMS_DOC,
                        "Thermal detection, not proof of burning type or pollution causation. "
                        "Confidence l/n/h is categorical, not a probability.",
                    ),
                )
            )
        return fires
