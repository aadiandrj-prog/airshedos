"""Operational checklist v1. Source units and QA are never reinterpreted as probabilities."""

from math import atan2, cos, degrees, radians, sin

from app.citizen.models import VisualObservation
from app.corroboration.models import (
    CorroborationRuleResult,
    EventFamily,
    EvidenceReference,
    StructuredReport,
    Verdict,
)
from app.corroboration.settings import CorroborationSettings
from app.environment.geo import haversine_km
from app.environment.models import EnvironmentalContext

FAMILIES = {
    "open_burning": EventFamily.COMBUSTION,
    "fire_or_combustion": EventFamily.COMBUSTION,
    "industrial_smoke": EventFamily.COMBUSTION,
    "construction_dust": EventFamily.DUST,
    "road_dust": EventFamily.DUST,
    "haze_or_smog": EventFamily.ATMOSPHERIC_HAZE,
    "vehicular_emissions": EventFamily.TRAFFIC,
}
AVAILABLE = {"live", "cached"}
POSITIVE = {Verdict.SUPPORTS, Verdict.WEAKLY_SUPPORTS}


def bearing_degrees(lat1, lng1, lat2, lng2):
    """Initial great-circle bearing from the fire to the report, clockwise from north."""
    a, b, delta = radians(lat1), radians(lat2), radians(lng2 - lng1)
    return degrees(atan2(sin(delta) * cos(b), cos(a) * sin(b) - sin(a) * cos(b) * cos(delta))) % 360


def angular_difference(a, b):
    return abs((a - b + 180) % 360 - 180)


class RuleEvaluation:
    def __init__(
        self,
        record: StructuredReport,
        context: EnvironmentalContext,
        settings: CorroborationSettings,
    ):
        self.record, self.context, self.settings = record, context, settings
        self.now = context.generated_at
        self.family = FAMILIES.get(record.analysis.event_type, EventFamily.NONE_OR_UNCERTAIN)

    def age(self, observed_at):
        return (self.now - observed_at).total_seconds()

    def reference(self, observation, source_id=None):
        return EvidenceReference(
            source_id=source_id or observation.provenance.source_id,
            observed_at=observation.observed_at,
            retrieved_at=observation.retrieved_at,
            age_seconds=self.age(observation.observed_at),
            submission_offset_seconds=(
                observation.observed_at - self.record.report.created_at
            ).total_seconds(),
            provenance=observation.provenance,
        )

    def result(self, rule_id, source, verdict, summary, inputs=None, refs=None):
        return CorroborationRuleResult(
            rule_id=rule_id,
            source=source,
            verdict=verdict,
            summary=summary,
            inputs_used=inputs or {},
            evidence_references=refs or [],
            generated_at=self.now,
        )

    def time_verdict(self, age, max_hours):
        if age < -self.settings.future_tolerance_seconds:
            return Verdict.UNAVAILABLE
        if age > max_hours * 3600:
            return Verdict.STALE
        return None

    def citizen(self):
        a = self.record.analysis
        inputs = {
            "event_type": a.event_type.value,
            "ordinal_confidence": a.event_type_confidence,
            "visible_smoke": a.visible_smoke,
            "visible_flames": a.visible_flames,
            "visible_dust": a.visible_dust,
            "visual_observations": [item.value for item in a.visual_observations],
            "capture_time_known": False,
            "citizen_text_contributes": False,
        }
        verdict, message = (
            Verdict.NEUTRAL,
            "Visual interpretation does not support an event family.",
        )
        # Actual internal disagreement, not an invented cross-provider physical contradiction.
        if VisualObservation.NO_FEATURES in a.visual_observations and any(
            flag is True for flag in (a.visible_smoke, a.visible_flames, a.visible_dust)
        ):
            verdict = Verdict.CONTRADICTS
            message = (
                "The no-feature observation disagrees with its own positive smoke/flame/dust "
                "flags. Review the interpretation; this is not an environmental contradiction."
            )
        elif self.family != EventFamily.NONE_OR_UNCERTAIN:
            if a.event_type_confidence == "high":
                verdict, message = (
                    Verdict.SUPPORTS,
                    "High ordinal visual support for a possible event.",
                )
            elif a.event_type_confidence == "medium":
                verdict, message = (
                    Verdict.WEAKLY_SUPPORTS,
                    "Medium ordinal visual support for a possible event.",
                )
        ref = EvidenceReference(
            source_id=self.record.evidence.id,
            observed_at=None,
            retrieved_at=a.analyzed_at,
            age_seconds=None,
            submission_offset_seconds=None,
            provenance=a.provenance,
        )
        return self.result("CITIZEN.VISUAL.v1", "Citizen visual", verdict, message, inputs, [ref])

    def air_quality(self):
        c, s = self.context, self.settings
        obs, status = c.air_quality, c.source_statuses.air_quality
        inputs = {
            "provider_status": status.status,
            "index_required": "ind_cpcb",
            "max_age_hours": s.aq_max_age_hours,
            "neutral_max": 100,
            "weak_max": 200,
            "valid_max": 500,
        }
        refs = [self.reference(obs)] if obs else []

        def result(v, msg):
            return self.result("AQ.CPCB.v1", "Current air quality", v, msg, inputs, refs)

        if status.status not in AVAILABLE or obs is None:
            return result(Verdict.UNAVAILABLE, "Current AQ context is unavailable.")
        inputs["age_seconds"] = self.age(obs.observed_at)
        if verdict := self.time_verdict(inputs["age_seconds"], s.aq_max_age_hours):
            return result(
                verdict, "AQ timestamp is stale or outside the allowed future clock skew."
            )
        index = next((i for i in obs.indexes if i.code == "ind_cpcb"), None)
        inputs.update(
            {
                "cpcb_aqi": index.value if index else None,
                "dominant_pollutant": index.dominant_pollutant if index else None,
            }
        )
        if index is None or index.value is None:
            return result(
                Verdict.NEUTRAL, "Provider did not return a CPCB index; no custom conversion."
            )
        if not 0 <= index.value <= 500:
            return result(
                Verdict.UNAVAILABLE, "CPCB index lies outside its documented 0–500 range."
            )
        if self.family == EventFamily.NONE_OR_UNCERTAIN:
            return result(
                Verdict.NEUTRAL, "Regional AQ context does not establish an event in this image."
            )
        allowed = {"pm10"} if self.family == EventFamily.DUST else {"pm10", "pm25"}
        inputs["eligible_dominant_pollutants"] = sorted(allowed)
        if index.dominant_pollutant not in allowed:
            return result(
                Verdict.NEUTRAL,
                "CPCB dominant pollutant does not meet this family's particulate rule.",
            )
        if index.value <= 100:
            return result(
                Verdict.NEUTRAL, f"CPCB AQI {index.value:g} adds no regional particulate support."
            )
        verdict = Verdict.WEAKLY_SUPPORTS if index.value <= 200 else Verdict.SUPPORTS
        return result(
            verdict,
            f"CPCB AQI {index.value:g}, dominated by {index.dominant_pollutant}, "
            "adds regional particulate context; it cannot identify the source category.",
        )

    def fire_candidates(self):
        s, report = self.settings, self.record.report
        candidates = []
        for obs in self.context.fires or []:
            distance = haversine_km(obs.latitude, obs.longitude, report.latitude, report.longitude)
            age = self.age(obs.observed_at)
            reason = "eligible"
            if self.time_verdict(age, s.fires_max_age_hours):
                reason = "stale" if age > s.fires_max_age_hours * 3600 else "future_timestamp"
            elif obs.confidence not in {"n", "h"}:
                reason = "low_or_unknown_confidence"
            elif distance > s.fire_regional_km:
                reason = "too_distant"
            elif distance > s.fire_near_km:
                reason = "regional_only"
            candidates.append(
                (
                    obs,
                    {
                        "source_id": obs.source_id,
                        "distance_km": distance,
                        "age_seconds": age,
                        "confidence": obs.confidence,
                        "eligibility": reason,
                    },
                )
            )
        return sorted(candidates, key=lambda item: (item[1]["distance_km"], item[0].source_id))

    def fires(self):
        c, s = self.context, self.settings
        candidates = self.fire_candidates()
        inputs = {
            "provider_status": c.source_statuses.fires.status,
            "very_near_km": s.fire_very_near_km,
            "near_km": s.fire_near_km,
            "regional_km": s.fire_regional_km,
            "max_age_hours": s.fires_max_age_hours,
            "strong_age_hours": s.fires_strong_age_hours,
            "accepted_confidence": ["n", "h"],
            "candidates": [data for _, data in candidates],
        }
        refs = [self.reference(obs, obs.source_id) for obs, _ in candidates]

        def result(v, msg):
            return self.result("FIRMS.PROXIMITY.v1", "Nearby fire", v, msg, inputs, refs)

        if self.family != EventFamily.COMBUSTION:
            return result(
                Verdict.NOT_APPLICABLE, "Active-fire detections do not support this event family."
            )
        if c.source_statuses.fires.status not in AVAILABLE or c.fires is None:
            return result(Verdict.UNAVAILABLE, "FIRMS active-fire context is unavailable.")
        eligible = [(obs, data) for obs, data in candidates if data["eligibility"] == "eligible"]
        if not eligible:
            if candidates and all(d["eligibility"] == "stale" for _, d in candidates):
                return result(
                    Verdict.STALE, "All fire detections exceed the recent-evidence age limit."
                )
            return result(
                Verdict.NEUTRAL,
                "No eligible nearby recent fire detection adds support; "
                "absence does not rule out combustion.",
            )
        strong = [
            (obs, data)
            for obs, data in eligible
            if data["distance_km"] <= s.fire_very_near_km
            and data["age_seconds"] <= s.fires_strong_age_hours * 3600
        ]
        _, best = (strong or eligible)[0]
        inputs["selected_source_id"] = best["source_id"]
        return result(
            Verdict.SUPPORTS if strong else Verdict.WEAKLY_SUPPORTS,
            f"Recent nominal/high-confidence active-fire detection {best['distance_km']:.1f} km "
            f"away, {max(0, best['age_seconds']) / 3600:.1f} h old; regional combustion context.",
        )

    def wind(self):
        c, s, report = self.context, self.settings, self.record.report
        obs = c.weather
        inputs = {
            "provider_status": c.source_statuses.weather.status,
            "max_age_hours": s.weather_max_age_hours,
            "tolerance_degrees": s.wind_tolerance_degrees,
            "min_speed_mps": s.wind_min_speed_mps,
            "max_fire_time_gap_hours": s.wind_fire_max_time_gap_hours,
            "near_km": s.fire_near_km,
            "fire_max_age_hours": s.fires_strong_age_hours,
        }
        refs = [self.reference(obs)] if obs else []

        def result(v, msg):
            return self.result("WEATHER.WIND.v1", "Wind consistency", v, msg, inputs, refs)

        if c.source_statuses.weather.status not in AVAILABLE or obs is None:
            return result(Verdict.UNAVAILABLE, "Weather context is unavailable.")
        inputs["age_seconds"] = self.age(obs.observed_at)
        if verdict := self.time_verdict(inputs["age_seconds"], s.weather_max_age_hours):
            return result(
                verdict, "Weather timestamp is stale or outside the allowed future clock skew."
            )
        if self.family != EventFamily.COMBUSTION:
            return result(
                Verdict.NOT_APPLICABLE, "Wind alone is context, not evidence of pollution."
            )
        if c.source_statuses.fires.status not in AVAILABLE:
            return result(
                Verdict.NEUTRAL, "Wind comparison needs an available nearby fire candidate."
            )
        eligible = [
            (fire, data)
            for fire, data in self.fire_candidates()
            if data["eligibility"] == "eligible"
            and data["age_seconds"] <= s.fires_strong_age_hours * 3600
        ]
        if not eligible:
            return result(Verdict.NEUTRAL, "No eligible recent fire candidate for wind comparison.")
        fire, data = eligible[0]  # Nearest; never cherry-pick a farther aligned fire.
        refs.append(self.reference(fire, fire.source_id))
        inputs.update(
            {
                "fire_source_id": fire.source_id,
                "fire_distance_km": data["distance_km"],
                "fire_age_seconds": data["age_seconds"],
                "wind_from_degrees": obs.wind_from_degrees,
                "speed_value": obs.wind_speed.value if obs.wind_speed else None,
                "speed_unit": obs.wind_speed.unit if obs.wind_speed else None,
            }
        )
        gap = abs((obs.observed_at - fire.observed_at).total_seconds())
        inputs["fire_weather_time_gap_seconds"] = gap
        if gap > s.wind_fire_max_time_gap_hours * 3600:
            return result(
                Verdict.NEUTRAL,
                "Fire and weather observations are too far apart in time for wind comparison.",
            )
        factors = {
            "KILOMETERS_PER_HOUR": 1 / 3.6,
            "METERS_PER_SECOND": 1,
            "MILES_PER_HOUR": 0.44704,
        }
        speed = (
            obs.wind_speed.value * factors[obs.wind_speed.unit]
            if obs.wind_speed and obs.wind_speed.unit in factors
            else None
        )
        inputs["speed_mps"] = speed
        if speed is None or speed < s.wind_min_speed_mps or obs.wind_from_degrees is None:
            return result(
                Verdict.NEUTRAL,
                "Wind direction/speed is missing, unsupported or too calm for comparison.",
            )
        if data["distance_km"] < 0.1:
            return result(
                Verdict.NEUTRAL,
                "Near-coincident coordinates make a directional comparison unhelpful.",
            )
        bearing = bearing_degrees(fire.latitude, fire.longitude, report.latitude, report.longitude)
        transport = (obs.wind_from_degrees + 180) % 360
        angle = angular_difference(transport, bearing)
        inputs.update(
            {
                "fire_to_report_bearing_degrees": bearing,
                "transport_degrees": transport,
                "angular_difference_degrees": angle,
            }
        )
        if angle <= s.wind_tolerance_degrees:
            return result(
                Verdict.WEAKLY_SUPPORTS,
                "Approximate wind transport aligns with fire-to-report bearing; "
                "conditional consistency only, not a plume or causal model.",
            )
        return result(
            Verdict.NEUTRAL,
            "Wind does not add directional support; local variability prevents contradiction.",
        )

    def satellite(self, product):
        s, satellite = self.settings, self.context.satellite
        item = (
            next((p for p in satellite.products if p.product == product), None)
            if satellite
            else None
        )
        obs = item.observation if item else None
        inputs = {
            "product": product,
            "provider_status": item.status if item else "unavailable",
            "availability": item.availability if item else "not_requested",
            "max_age_hours": s.satellite_max_age_hours,
            "contributes_to_support": False,
        }
        refs = [self.reference(obs, obs.image_id)] if obs else []
        verdict, message = Verdict.UNAVAILABLE, "No usable satellite observation is available."
        if item and item.status in AVAILABLE and item.availability == "available" and obs:
            age = self.age(obs.observed_at)
            inputs.update(
                {
                    "value": obs.value,
                    "unit": obs.unit,
                    "collection": obs.collection,
                    "band": obs.band,
                    "quality": obs.quality.status,
                    "age_seconds": age,
                }
            )
            verdict = self.time_verdict(age, s.satellite_max_age_hours) or Verdict.NEUTRAL
            message = (
                "Latest usable satellite observation is context only; native atmospheric "
                "columns/aerosol index do not establish ground concentration or event causality."
            )
            if verdict == Verdict.STALE:
                message = "Usable satellite observation exceeds the age limit; context only."
            elif verdict == Verdict.UNAVAILABLE:
                message = "Satellite timestamp exceeds the allowed future clock skew."
        return self.result(
            f"SATELLITE.{product.upper()}.v1",
            f"Sentinel-5P {product}",
            verdict,
            message,
            inputs,
            refs,
        )

    def evaluate(self):
        return [
            self.citizen(),
            self.air_quality(),
            self.fires(),
            self.wind(),
            *(self.satellite(p) for p in ("no2", "co", "aerosol_index")),
        ]
