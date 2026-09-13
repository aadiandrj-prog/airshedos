import os

from pydantic import Field, model_validator

from app.models import DomainModel


class CorroborationSettings(DomainModel):
    # These are inspectable MVP policy bands, not calibrated detection thresholds.
    report_ttl_seconds: int = Field(default=1800, ge=60, le=3600)
    report_max_entries: int = Field(default=256, ge=1, le=1024)
    aq_max_age_hours: float = Field(default=2, gt=0, le=24)
    weather_max_age_hours: float = Field(default=1, gt=0, le=24)
    fires_max_age_hours: float = Field(default=24, gt=0, le=72)
    fires_strong_age_hours: float = Field(default=6, gt=0, le=24)
    satellite_max_age_hours: float = Field(default=24, gt=0, le=72)
    fire_very_near_km: float = Field(default=5, gt=0, le=25)
    fire_near_km: float = Field(default=15, gt=0, le=50)
    fire_regional_km: float = Field(default=25, gt=0, le=100)
    wind_tolerance_degrees: float = Field(default=45, gt=0, le=90)
    wind_min_speed_mps: float = Field(default=1, gt=0, le=10)
    wind_fire_max_time_gap_hours: float = Field(default=1, gt=0, le=6)
    future_tolerance_seconds: float = Field(default=300, ge=0, le=600)

    @model_validator(mode="after")
    def ordered_bands(self):
        if not self.fire_very_near_km <= self.fire_near_km <= self.fire_regional_km:
            raise ValueError("Fire distance bands must be ordered")
        if self.fires_strong_age_hours > self.fires_max_age_hours:
            raise ValueError("Strong fire age must fit recent window")
        return self

    @classmethod
    def from_env(cls):
        return cls(
            **{
                name: os.environ[f"CORROBORATION_{name.upper()}"]
                for name in cls.model_fields
                if os.environ.get(f"CORROBORATION_{name.upper()}")
            }
        )
