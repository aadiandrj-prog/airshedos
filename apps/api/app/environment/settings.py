import os
from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class EnvironmentSettings(BaseModel):
    google_key: SecretStr = SecretStr("")
    firms_key: SecretStr = SecretStr("")
    timeout_seconds: float = Field(default=8, ge=1, le=30)
    cache_ttl_seconds: int = Field(default=600, ge=0, le=3600)
    firms_cache_ttl_seconds: int = Field(default=900, ge=0, le=3600)
    firms_dataset: Literal["VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT", "VIIRS_SNPP_NRT"] = (
        "VIIRS_NOAA20_NRT"
    )
    firms_radius_km: float = Field(default=25, ge=1, le=100)
    earth_engine_project: str = ""
    satellite_lookback_hours: int = Field(default=72, ge=1, le=168)
    satellite_radius_km: float = Field(default=10, ge=1, le=25)
    satellite_cache_ttl_seconds: int = Field(default=3600, ge=0, le=7200)
    satellite_timeout_seconds: float = Field(default=25, ge=1, le=60)
    cache_max_entries: int = Field(default=256, ge=1, le=1024)

    @classmethod
    def from_env(cls):
        return cls(
            earth_engine_project=(
                os.getenv("EARTH_ENGINE_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT", "")
            ).strip(),
            satellite_lookback_hours=os.getenv("SATELLITE_LOOKBACK_HOURS", "72"),
            satellite_radius_km=os.getenv("SATELLITE_RADIUS_KM", "10"),
            satellite_cache_ttl_seconds=os.getenv("SATELLITE_CACHE_TTL_SECONDS", "3600"),
            satellite_timeout_seconds=os.getenv("SATELLITE_TIMEOUT_SECONDS", "25"),
            google_key=os.getenv("GOOGLE_MAPS_PLATFORM_API_KEY", "").strip(),
            firms_key=os.getenv("NASA_FIRMS_MAP_KEY", "").strip(),
            timeout_seconds=os.getenv("ENVIRONMENT_HTTP_TIMEOUT_SECONDS", "8"),
            cache_ttl_seconds=os.getenv("ENVIRONMENT_CACHE_TTL_SECONDS", "600"),
            firms_cache_ttl_seconds=os.getenv("FIRMS_CACHE_TTL_SECONDS", "900"),
            firms_dataset=os.getenv("FIRMS_DATASET", "VIIRS_NOAA20_NRT"),
            firms_radius_km=os.getenv("FIRMS_SEARCH_RADIUS_KM", "25"),
        )
