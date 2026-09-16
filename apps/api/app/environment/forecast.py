"""Official Google forecast adapter and transparent arithmetic summaries."""

from datetime import UTC, datetime, timedelta
from typing import Protocol

from app.environment.forecast_models import (
    ForecastSummary,
    ForecastWindow,
    HourlyAirQualityForecast,
)
from app.environment.models import AirQualityIndex, Measurement, PollutantMeasurement
from app.environment.providers import measurement, provenance

FORECAST_DOC = "https://developers.google.com/maps/documentation/air-quality/forecast"
OPTIONS = ("LOCAL_AQI", "POLLUTANT_CONCENTRATION")
NATIVE_PM_UNIT = "MICROGRAMS_PER_CUBIC_METER"


def forecast_provenance():
    return provenance(
        "google_air_quality_forecast",
        "Google forecast:lookup; deterministic horizon summaries",
        FORECAST_DOC,
        "External provider forecast, not an AirshedOS-trained prediction. Native units and "
        "index identity retained. Valid times are not issuance times. No causal attribution.",
    )


class ForecastProvider(Protocol):
    name: str
    configured: bool

    async def fetch(self, lat, lng, start, end) -> dict | None: ...


class GoogleAirQualityForecastProvider:
    name = "google_air_quality_forecast"

    def __init__(self, http, key):
        self.http, self._key, self.configured = http, key, bool(key)

    async def fetch(self, lat, lng, start, end):
        body = {
            "location": {"latitude": lat, "longitude": lng},
            "period": {"startTime": start.isoformat(), "endTime": end.isoformat()},
            "pageSize": 24,
            "universalAqi": True,
            "extraComputations": list(OPTIONS),
            "languageCode": "en",
        }
        rows, tokens, region = [], set(), None
        # Normally one page; reject pagination cycles and truncation.
        for _ in range(4):
            response = await self.http.request(
                "POST",
                "https://airquality.googleapis.com/v1/forecast:lookup",
                headers={"X-Goog-Api-Key": self._key},
                json=body,
            )
            raw = response.json()
            if not isinstance(raw, dict) or not isinstance(raw.get("hourlyForecasts", []), list):
                raise ValueError("Malformed forecast")
            returned_region = raw.get("regionCode")
            if region and returned_region and region != returned_region:
                raise ValueError("Inconsistent forecast region")
            region = region or returned_region
            for hour in raw.get("hourlyForecasts", []):
                item = HourlyAirQualityForecast(
                    forecast_at=hour["dateTime"],
                    indexes=[
                        AirQualityIndex(
                            code=i["code"],
                            display_name=i.get("displayName"),
                            value=i.get("aqi"),
                            category=i.get("category"),
                            dominant_pollutant=i.get("dominantPollutant"),
                        )
                        for i in hour.get("indexes", [])
                    ],
                    pollutants=[
                        PollutantMeasurement(
                            code=p["code"],
                            name=p.get("displayName"),
                            full_name=p.get("fullName"),
                            concentration=measurement(p.get("concentration"), unit="units"),
                        )
                        for p in hour.get("pollutants", [])
                    ],
                )
                item.forecast_at = item.forecast_at.astimezone(UTC)
                if (
                    not start <= item.forecast_at <= end
                    or item.forecast_at.minute
                    or item.forecast_at.second
                    or item.forecast_at.microsecond
                ):
                    raise ValueError("Forecast outside exact-hour query window")
                if len({i.code for i in item.indexes}) != len(item.indexes) or len(
                    {p.code for p in item.pollutants}
                ) != len(item.pollutants):
                    raise ValueError("Duplicate forecast product")
                if any(i.value is not None and i.value < 0 for i in item.indexes) or any(
                    p.concentration is not None and p.concentration.value < 0
                    for p in item.pollutants
                ):
                    raise ValueError("Negative forecast value")
                index = cpcb(item)
                item.dominant_pollutant = index.dominant_pollutant if index else None
                # Empty hour metadata is not usable forecast coverage.
                if any(i.value is not None for i in item.indexes) or any(
                    p.concentration is not None for p in item.pollutants
                ):
                    rows.append(item)
            token = raw.get("nextPageToken")
            if not token:
                break
            if not isinstance(token, str) or token in tokens:
                raise ValueError("Invalid forecast pagination")
            tokens.add(token)
            body = {**body, "pageToken": token}
        else:
            raise ValueError("Forecast pagination exceeded bound")
        if len({r.forecast_at for r in rows}) != len(rows):
            raise ValueError("Duplicate forecast hour")
        return (
            {
                "hourly_forecasts": sorted(rows, key=lambda r: r.forecast_at),
                "region_code": region,
                "retrieved_at": datetime.now(UTC),
            }
            if rows
            else None
        )


def cpcb(observation):
    return next(
        (i for i in observation.indexes if i.code == "ind_cpcb" and i.value is not None), None
    )


def concentration(observation, code):
    return next(
        (
            p.concentration
            for p in observation.pollutants
            if p.code == code and p.concentration is not None
        ),
        None,
    )


def classify(current, peak):
    delta = peak - current
    if delta >= max(25, current * 0.50):
        return "SHARPLY_WORSENING"
    if delta >= max(5, current * 0.10):
        return "WORSENING"
    if delta <= -max(5, current * 0.10):
        return "IMPROVING"
    return "STABLE"


def summarize(rows, anchor, horizon, current, requested):
    start, end = anchor + timedelta(hours=1), anchor + timedelta(hours=horizon)
    hours = [r for r in rows if start <= r.forecast_at <= end]

    def peak(code):
        pairs = [(r, concentration(r, code)) for r in hours if concentration(r, code) is not None]
        # Never rank concentrations expressed in incompatible units.
        if not pairs or len({m.unit for _, m in pairs}) != 1:
            return None, None, 0
        row, value = max(pairs, key=lambda pair: (pair[1].value, -pair[0].forecast_at.timestamp()))
        return value, row.forecast_at, len(pairs)

    pm25, at, pm25_hours = peak("pm25")
    pm10, pm10_at, _ = peak("pm10")
    indexes = [(r, cpcb(r)) for r in hours if cpcb(r)]
    index_row, index = (
        max(indexes, key=lambda pair: (pair[1].value, -pair[0].forecast_at.timestamp()))
        if indexes
        else (None, None)
    )
    delta = relative = None
    outlook, note = "UNAVAILABLE", "Current PM2.5 unavailable; no comparison inferred."
    current_pm = concentration(current, "pm25") if current else None
    if current_pm and pm25:
        age = (requested - current.observed_at).total_seconds()
        if not -300 <= age <= 7200:
            note = "Current AQ is stale or future-dated; comparison withheld."
        elif current_pm.unit != pm25.unit:
            note = "Current and forecast PM2.5 units differ; comparison withheld."
        elif current_pm.value < 0:
            note = "Current PM2.5 invalid; comparison withheld."
        else:
            change = pm25.value - current_pm.value
            delta = Measurement(value=change, unit=pm25.unit)
            relative = change / current_pm.value * 100 if current_pm.value > 0 else None
            note = (
                "Arithmetic difference from current PM2.5 to the forecast peak; not a probability."
            )
            if pm25.unit != NATIVE_PM_UNIT:
                note += " Descriptive thresholds require µg/m³; category withheld."
            elif pm25_hours != horizon:
                note += " PM2.5 coverage is incomplete; category withheld."
            else:
                outlook = classify(current_pm.value, pm25.value)
    elif not pm25:
        note = "Forecast PM2.5 unavailable or units inconsistent; no comparison inferred."
    return ForecastSummary(
        horizon_hours=horizon,
        window=ForecastWindow(start=start, end=end),
        available_hours=len(hours),
        pm25_hours=pm25_hours,
        cpcb_hours=len(indexes),
        coverage="complete" if len(hours) == horizon else "partial" if hours else "none",
        max_cpcb_aqi=index.value if index else None,
        max_pm25=pm25,
        max_pm10=pm10,
        worst_category=index.category if index else None,
        peak_at=at or (index_row.forecast_at if index_row else None),
        peak_basis="pm25" if at else "ind_cpcb" if index_row else None,
        cpcb_peak_at=index_row.forecast_at if index_row else None,
        pm10_peak_at=pm10_at,
        delta_pm25_vs_current=delta,
        relative_pm25_change_percent=relative,
        outlook=outlook,
        comparison_note=note,
    )
