"""Provider outlook, never a corroboration vote or an AirshedOS-trained prediction."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, FiniteFloat

from app.environment.models import (
    AirQualityIndex,
    AirQualityObservation,
    EnvironmentalProvenance,
    EnvironmentalSourceStatus,
    Measurement,
    PollutantMeasurement,
)
from app.models import DomainModel, Latitude, Longitude

ForecastHorizon = Literal[6, 12, 24]


class HourlyAirQualityForecast(DomainModel):
    forecast_at: AwareDatetime
    indexes: list[AirQualityIndex]
    pollutants: list[PollutantMeasurement]
    dominant_pollutant: str | None = None


class ForecastWindow(DomainModel):
    start: AwareDatetime
    end: AwareDatetime
    end_inclusive: Literal[True] = True


class ForecastSummary(DomainModel):
    horizon_hours: ForecastHorizon
    window: ForecastWindow
    available_hours: Annotated[int, Field(ge=0)]
    pm25_hours: Annotated[int, Field(ge=0)]
    cpcb_hours: Annotated[int, Field(ge=0)]
    coverage: Literal["complete", "partial", "none"]
    max_cpcb_aqi: FiniteFloat | None = None
    max_pm25: Measurement | None = None
    max_pm10: Measurement | None = None
    worst_category: str | None = None
    peak_at: AwareDatetime | None = None
    peak_basis: Literal["pm25", "ind_cpcb"] | None = None
    cpcb_peak_at: AwareDatetime | None = None
    pm10_peak_at: AwareDatetime | None = None
    delta_pm25_vs_current: Measurement | None = None
    relative_pm25_change_percent: FiniteFloat | None = None
    outlook: Literal["IMPROVING", "STABLE", "WORSENING", "SHARPLY_WORSENING", "UNAVAILABLE"]
    comparison_note: str


class AirQualityForecastContext(DomainModel):
    latitude: Latitude
    longitude: Longitude
    requested_at: AwareDatetime
    generated_at: AwareDatetime
    requested_horizon_hours: ForecastHorizon
    provider: Literal["google_air_quality_forecast"] = "google_air_quality_forecast"
    provider_status: EnvironmentalSourceStatus
    window: ForecastWindow
    retrieved_at: AwareDatetime | None = None
    # Google forecast.lookup supplies valid times, not the model run/issuance time.
    issued_at: AwareDatetime | None = None
    region_code: str | None = None
    hourly_forecasts: list[HourlyAirQualityForecast]
    summaries: list[ForecastSummary]
    current_air_quality: AirQualityObservation | None = None
    current_source_status: EnvironmentalSourceStatus
    provenance: EnvironmentalProvenance
    independence_note: str = (
        "Google current AQ and forecast AQ share a provider/model ecosystem. "
        "Forecast is an operational outlook, not an independent corroboration source; "
        "it does not change corroboration support."
    )
    temporal_note: str = (
        "Hourly forecast valid times, starting next UTC hour. Retrieval time is not issuance time. "
        "Summaries describe available forecast points, not measured future outcomes."
    )
    policy_version: Literal["provider_forecast_v1"] = "provider_forecast_v1"
