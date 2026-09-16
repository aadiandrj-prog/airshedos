"""Explicit train/serve profiles. Conditional assumptions are not publication-time proof."""

import re

from prediction.common import ERA5_BANDS, DatasetError

OPERATIONAL_V1 = "OPERATIONAL_V1"
RESEARCH_ENRICHED_V1 = "RESEARCH_ENRICHED_V1"
# Initial live September 2026 sample was ~69 hours stale. Revalidate prospectively.
DEFAULT_AQ_BUFFER_HOURS = 72
CALENDAR = {"hour_of_day", "day_of_week", "month", "weekend"}


def availability_manifest(features, config):
    operational = config.profile == OPERATIONAL_V1
    entries = []
    for name in features:
        if operational:
            lag = re.fullmatch(
                r"(?:pm25|(?:pm10|no2|co|o3|so2)_(?:ug_m3|ppb|ppm))_lag_(\d+)h", name
            )
            safe_name = (
                name in CALENDAR
                or name in {"pm25_latest_available", "history_count_30d"}
                or re.fullmatch(r"pm25_rolling_(?:mean|std)_(?:3|6|12|24)h", name)
                or re.fullmatch(r"trailing_30d_p(?:85|90|95)_pm25", name)
                or (lag and int(lag.group(1)) >= config.aq_availability_buffer_hours)
            )
            if name in {"pm25_rolling_mean_24h", "pm25_rolling_std_24h"}:
                safe_name = False
            if not safe_name:
                raise DatasetError("Unsafe or unknown feature in OPERATIONAL_V1: " + name)
        calendar = name in CALENDAR
        weather = name.startswith("era5_")
        aq = not calendar and not weather
        entries.append(
            {
                "feature_name": name,
                "included_in_profile": True,
                "source": "calendar"
                if calendar
                else "ECMWF/ERA5_LAND/HOURLY"
                if weather
                else "OpenAQ v3 hours",
                "historical_availability": "deterministic"
                if calendar
                else "retrieved snapshot; release time unverified",
                "assumed_operational_availability": (
                    "known at forecast origin"
                    if calendar
                    else "not current at forecast origin"
                    if weather
                    else "measurement interval end <= forecast origin minus configured buffer"
                ),
                "availability_buffer_hours": config.aq_availability_buffer_hours
                if aq and operational
                else 0,
                "deployment_safe": calendar or (aq and operational),
                "conditional": aq and operational,
                "reason": (
                    "deterministic calendar"
                    if calendar
                    else "retrospective source publication delay"
                    if weather
                    else "conditional buffer; unobserved historical revisions remain a risk"
                    if operational
                    else "unbuffered retrospective observation"
                ),
                "known_revision_risk": "none"
                if calendar
                else "historical revisions not identifiable from this snapshot",
            }
        )
    excluded = []
    if operational:
        for name in [
            *[f"era5_{band}" for band in ERA5_BANDS],
            "era5_wind_speed_mps",
            "era5_wind_from_degrees",
            "pm25_rolling_mean_24h",
            "pm25_rolling_std_24h",
        ]:
            weather = name.startswith("era5_")
            excluded.append(
                {
                    "feature_name": name,
                    "included_in_profile": False,
                    "source": "ECMWF/ERA5_LAND/HOURLY" if weather else "OpenAQ v3 hours",
                    "historical_availability": "retrospective"
                    if weather
                    else "unavailable in inspected CPCB gate",
                    "assumed_operational_availability": "not admitted to this operational profile",
                    "availability_buffer_hours": None
                    if weather
                    else config.aq_availability_buffer_hours,
                    "deployment_safe": False,
                    "conditional": False,
                    "reason": "retrospective publication delay"
                    if weather
                    else "daily sub-75% hour prevents complete 24-hour windows; QA unchanged",
                    "known_revision_risk": "historical source revisions remain unverified",
                }
            )
    return {
        "excluded_candidate_features": excluded,
        "profile": config.profile,
        "aq_availability_buffer_hours": config.aq_availability_buffer_hours,
        "deployment_label": (
            "CONDITIONAL: validate publication lag and revisions before serving"
            if operational
            else "NOT DEPLOYMENT-SAFE AS CURRENTLY SOURCED"
        ),
        "prospective_publication_validation_complete": False,
        "historical_revision_freedom_proven": False,
        "features": entries,
    }


def validate_availability_manifest(manifest, features, config):
    expected = availability_manifest(features, config)
    if manifest != expected:
        raise DatasetError("Feature availability manifest and profile/columns disagree")
    if config.profile == OPERATIONAL_V1:
        if any(name.startswith("era5_") for name in features):
            raise DatasetError("ERA5 is forbidden in OPERATIONAL_V1")
        if any(not item["deployment_safe"] for item in manifest["features"]):
            raise DatasetError("Non-deployment-safe operational feature")
    return expected
