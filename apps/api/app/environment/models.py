from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, FiniteFloat

from app.models import DomainModel, Latitude, Longitude, Provenance


class SourceState(StrEnum):
    LIVE = "live"
    CACHED = "cached"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"
    ERROR = "error"


class EnvironmentalProvenance(Provenance):
    is_demo: Literal[False] = False
    documentation_url: str


class Measurement(DomainModel):
    value: FiniteFloat
    unit: str


class PollutantMeasurement(DomainModel):
    code: str
    name: str | None = None
    full_name: str | None = None
    concentration: Measurement | None = None


class AirQualityIndex(DomainModel):
    code: str
    display_name: str | None = None
    value: FiniteFloat | None = None
    category: str | None = None
    dominant_pollutant: str | None = None


class EnvironmentalObservation(DomainModel):
    latitude: Latitude
    longitude: Longitude
    observed_at: AwareDatetime
    retrieved_at: AwareDatetime
    status: Literal[SourceState.LIVE, SourceState.CACHED] = SourceState.LIVE
    provenance: EnvironmentalProvenance


class AirQualityObservation(EnvironmentalObservation):
    region_code: str | None = None
    indexes: list[AirQualityIndex]
    pollutants: list[PollutantMeasurement]


class MeteorologicalObservation(EnvironmentalObservation):
    temperature: Measurement | None = None
    relative_humidity_percent: Annotated[float, Field(ge=0, le=100)] | None = None
    wind_speed: Measurement | None = None
    wind_from_degrees: Annotated[float, Field(ge=0, lt=360)] | None = None
    wind_cardinal: str | None = None
    sea_level_pressure: Measurement | None = None
    precipitation_probability_percent: Annotated[float, Field(ge=0, le=100)] | None = None
    precipitation_qpf: Measurement | None = None
    cloud_cover_percent: Annotated[float, Field(ge=0, le=100)] | None = None


class FireObservation(EnvironmentalObservation):
    source_id: str
    description: Literal["Nearby active-fire detection"] = "Nearby active-fire detection"
    # VIIRS l/n/h are source categories, not probabilities.
    confidence: Literal["l", "n", "h"] | None = None
    satellite: str | None = None
    instrument: str | None = None
    brightness: Measurement | None = None
    fire_radiative_power: Measurement | None = None
    distance_from_query_km: Annotated[float, Field(ge=0)]


class EnvironmentalSourceStatus(DomainModel):
    provider: str
    configured: bool
    status: SourceState
    message: str
    retrieved_at: AwareDatetime | None = None
    latency_ms: Annotated[float, Field(ge=0)]


class EnvironmentalSourceStatuses(DomainModel):
    air_quality: EnvironmentalSourceStatus
    weather: EnvironmentalSourceStatus
    fires: EnvironmentalSourceStatus


class ProviderConfiguration(DomainModel):
    provider: str
    configured: bool
    # Configuration is not a network/health probe.
    configuration_state: Literal["configured", "not_configured"]


class EnvironmentalSources(DomainModel):
    air_quality: ProviderConfiguration
    weather: ProviderConfiguration
    fires: ProviderConfiguration


SatelliteProduct = Literal["no2", "co", "aerosol_index"]
SatelliteAvailability = Literal[
    "available",
    "no_scene",
    "quality_filtered",
    "no_usable_pixels",
    "not_configured",
    "authentication_error",
    "configuration_error",
    "provider_error",
    "timeout",
    "busy",
]


class SatelliteSearchWindow(DomainModel):
    start: AwareDatetime
    end: AwareDatetime
    lookback_hours: Annotated[int, Field(ge=1, le=168)]
    end_mode: Literal["explicit", "current_hour"]


class SatelliteQuality(DomainModel):
    status: Literal["usable"] = "usable"
    catalog_qa_rule: str
    scene_quality: Literal["Nominal", "NOMINAL"]
    processing_status: Literal["Nominal", "NRTI-processing product"]
    valid_grid_cells: Annotated[int, Field(gt=0)]
    applied_filters: list[str]
    note: str = (
        "L3 ingestion QA is upstream; original per-pixel QA is not exposed. Not a confidence score."
    )


class SatelliteObservation(DomainModel):
    product: SatelliteProduct
    value: FiniteFloat
    unit: Literal["mol/m²", "dimensionless"]
    observed_at: AwareDatetime
    retrieved_at: AwareDatetime
    age_seconds: Annotated[float, Field(ge=0)]
    collection: str
    band: str
    image_id: str
    source_product_id: str | None = None
    grid_scale_m: float
    native_footprint: str | None = None
    retrieval_radius_km: float
    statistic: Literal["mean"] = "mean"
    quality: SatelliteQuality
    provenance: EnvironmentalProvenance


class SatelliteProductResult(DomainModel):
    product: SatelliteProduct
    status: SourceState
    availability: SatelliteAvailability
    message: str
    collection: str
    band: str
    unit: Literal["mol/m²", "dimensionless"]
    observation: SatelliteObservation | None = None
    scene_count: Annotated[int, Field(ge=0)] | None = None
    quality_scene_count: Annotated[int, Field(ge=0)] | None = None
    latency_ms: Annotated[float, Field(ge=0)] = 0
    cache_hit: bool = False


class SatelliteAtmosphericContext(DomainModel):
    latitude: Latitude
    longitude: Longitude
    query_latitude: Latitude
    query_longitude: Longitude
    requested_at: AwareDatetime
    generated_at: AwareDatetime
    search_window: SatelliteSearchWindow
    retrieval_radius_km: float
    grid_scale_m: float
    products: list[SatelliteProductResult]
    provider_status: EnvironmentalSourceStatus
    availability: Literal["complete", "partial", "none"]
    provenance: EnvironmentalProvenance
    temporal_note: str = (
        "Latest usable observation per product; acquisition times may differ. Not real-time."
    )
    measurement_note: str = (
        "Satellite atmospheric columns are regional context and are not equivalent to "
        "ground-level pollutant concentrations."
    )


class EnvironmentalContext(DomainModel):
    latitude: Latitude
    longitude: Longitude
    requested_at: AwareDatetime
    generated_at: AwareDatetime
    requested_reference_time: AwareDatetime | None = None
    time_mode: Literal["current"] = "current"
    temporal_note: str = (
        "AQ, weather and FIRMS query current conditions. Satellite uses its explicit search window."
    )
    satellite: SatelliteAtmosphericContext | None = None
    air_quality: AirQualityObservation | None
    weather: MeteorologicalObservation | None
    # null = no valid response; [] = successful query with no nearby detections.
    fires: list[FireObservation] | None
    fire_dataset: str
    fire_search_radius_km: float
    fire_window_days: int
    source_statuses: EnvironmentalSourceStatuses
    incident_relationship: Literal["independent_context_not_demo_corroboration"] = (
        "independent_context_not_demo_corroboration"
    )
