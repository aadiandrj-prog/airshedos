"""Synthetic normalized evidence; no live external calls or scientific validation claims."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_citizen import FakeAnalyzer, picture

from app.citizen.models import CitizenAnalysisResponse
from app.corroboration.engine import assess
from app.corroboration.models import StructuredReport
from app.corroboration.repository import EphemeralReportRepository
from app.corroboration.rules import angular_difference, bearing_degrees
from app.corroboration.settings import CorroborationSettings
from app.environment.models import (
    EnvironmentalContext,
    FireObservation,
    SatelliteAtmosphericContext,
)
from app.main import create_app

FIXTURES = Path(__file__).parents[2] / "web/e2e/fixtures"
NOW = datetime(2026, 9, 13, 6, tzinfo=UTC)
SETTINGS = CorroborationSettings()


def report(event="open_burning", confidence="high", text="untrusted text"):
    response = CitizenAnalysisResponse.model_validate_json(
        (FIXTURES / "citizen.test.json").read_text()
    )
    response.report.created_at = NOW - timedelta(minutes=2)
    response.report.description = text
    a = response.analysis
    a.insufficient_evidence = False
    a.event_type = event
    a.event_type_confidence = confidence
    a.analyzed_at = NOW - timedelta(minutes=1)
    a.visible_smoke = event == "open_burning"
    a.visible_flames = event == "open_burning"
    a.visible_dust = event == "construction_dust"
    return StructuredReport(report=response.report, analysis=a, evidence=response.evidence)


def context(aqi=61, dominant="pm25"):
    c = EnvironmentalContext.model_validate_json((FIXTURES / "environment.test.json").read_text())
    c.generated_at = c.requested_at = NOW
    c.requested_reference_time = NOW - timedelta(minutes=2)
    for obs in (c.air_quality, c.weather):
        obs.observed_at = NOW - timedelta(minutes=30)
        obs.retrieved_at = NOW
    c.air_quality.indexes[1].value = aqi
    c.air_quality.indexes[1].dominant_pollutant = dominant
    c.fires = []
    c.satellite = None
    c.weather.wind_from_degrees = 180  # From south, transport north.
    return c


def fire(c, km=4, hours=0.5, confidence="n", source_id="test-fire"):
    item = json.loads((FIXTURES / "environment.test.json").read_text())["fires"][0]
    item.update(
        latitude=c.latitude - km / 111.19508,
        longitude=c.longitude,
        observed_at=(NOW - timedelta(hours=hours)).isoformat(),
        retrieved_at=NOW.isoformat(),
        confidence=confidence,
        distance_from_query_km=999,
        source_id=source_id,
    )
    c.fires.append(FireObservation.model_validate(item))
    return c


def rule(result, prefix):
    return next(r for r in result.rules if r.rule_id.startswith(prefix))


def run(c=None, r=None, settings=SETTINGS):
    return assess(r or report(), c or context(), settings)


def unavailable(c):
    c.air_quality = c.weather = c.fires = None
    c.satellite = None
    for status in (
        c.source_statuses.air_quality,
        c.source_statuses.weather,
        c.source_statuses.fires,
    ):
        status.status = "unavailable"
    return c


def test_strong_combustion_and_downwind():
    result = run(fire(context()))
    assert result.support_level == "STRONG"
    assert result.recommended_next_step == "FIELD_VERIFICATION"
    assert rule(result, "WEATHER").verdict == "WEAKLY_SUPPORTS"
    assert rule(result, "FIRMS").inputs_used["candidates"][0]["distance_km"] == pytest.approx(
        4, abs=0.001
    )
    assert rule(result, "WEATHER").inputs_used["transport_degrees"] == 0
    assert result.temporal_basis == "submission_time_proxy"


@pytest.mark.parametrize(
    "km,hours,confidence,verdict,level",
    [
        (5, 6, "n", "SUPPORTS", "STRONG"),
        (5.01, 1, "h", "WEAKLY_SUPPORTS", "MODERATE"),
        (4, 6.01, "n", "WEAKLY_SUPPORTS", "MODERATE"),
        (15, 24, "n", "WEAKLY_SUPPORTS", "MODERATE"),
        (15.1, 1, "n", "NEUTRAL", "WEAK"),
        (25, 1, "n", "NEUTRAL", "WEAK"),
        (26, 1, "h", "NEUTRAL", "WEAK"),
        (4, 24.01, "h", "STALE", "WEAK"),
        (4, 1, "l", "NEUTRAL", "WEAK"),
        (4, 1, None, "NEUTRAL", "WEAK"),
    ],
)
def test_fire_policy(km, hours, confidence, verdict, level):
    # Latitude inverse is rounded downward by <0.1m to keep exact boundary inside.
    result = run(fire(context(), km=km - 0.00001, hours=hours, confidence=confidence))
    assert rule(result, "FIRMS").verdict == verdict
    assert result.support_level == level


@pytest.mark.parametrize(
    "aqi,verdict,level",
    [
        (0, "NEUTRAL", "WEAK"),
        (100, "NEUTRAL", "WEAK"),
        (101, "WEAKLY_SUPPORTS", "MODERATE"),
        (200, "WEAKLY_SUPPORTS", "MODERATE"),
        (201, "SUPPORTS", "MODERATE"),
        (500, "SUPPORTS", "MODERATE"),
        (501, "UNAVAILABLE", "WEAK"),
        (-1, "UNAVAILABLE", "WEAK"),
    ],
)
def test_cpcb_thresholds(aqi, verdict, level):
    result = run(context(aqi))
    assert rule(result, "AQ").verdict == verdict
    assert result.support_level == level
    assert rule(result, "FIRMS").verdict == "NEUTRAL"


@pytest.mark.parametrize(
    "dominant,verdict,level",
    [
        ("pm10", "SUPPORTS", "MODERATE"),
        ("pm25", "NEUTRAL", "WEAK"),
        ("no2", "NEUTRAL", "WEAK"),
        (None, "NEUTRAL", "WEAK"),
    ],
)
def test_dust_needs_pm10_not_fire(dominant, verdict, level):
    result = run(fire(context(250, dominant)), report("construction_dust"))
    assert rule(result, "AQ").verdict == verdict
    assert rule(result, "FIRMS").verdict == "NOT_APPLICABLE"
    assert result.support_level == level


def test_no_uaqi_or_raw_concentration_conversion():
    c = context(250)
    c.air_quality.indexes = c.air_quality.indexes[:1]
    c.air_quality.pollutants[0].concentration.value = 1000
    assert rule(run(c), "AQ").verdict == "NEUTRAL"


@pytest.mark.parametrize(
    "event,confidence", [("uncertain", "low"), ("no_visible_pollution", "high"), ("other", "high")]
)
def test_none_or_uncertain_never_confirmed_by_poor_environment(event, confidence):
    result = run(fire(context(450)), report(event, confidence))
    assert result.support_level == "INSUFFICIENT"
    assert all(r.verdict != "CONTRADICTS" for r in result.rules)
    assert rule(result, "AQ").verdict == "NEUTRAL"


def test_actual_structured_visual_disagreement_requires_review():
    r = report("no_visible_pollution")
    r.analysis.visible_flames = True
    from app.citizen.models import VisualObservation

    r.analysis.visual_observations = [VisualObservation.NO_FEATURES]
    result = run(context(50), r)
    assert result.support_level == "CONFLICTING"
    assert "own positive" in rule(result, "CITIZEN").summary
    assert result.recommended_next_step == "REVIEW"


@pytest.mark.parametrize("confidence,level", [("medium", "MODERATE"), ("low", "INSUFFICIENT")])
def test_ordinal_visual_policy(confidence, level):
    assert run(fire(context()), report(confidence=confidence)).support_level == level


def test_all_unavailable_and_one_provider_error():
    c = unavailable(context())
    assert run(c).support_level == "INSUFFICIENT"
    c = fire(context())
    c.air_quality = None
    c.source_statuses.air_quality.status = "error"
    result = run(c)
    assert result.support_level == "STRONG"
    assert rule(result, "AQ").verdict == "UNAVAILABLE"
    assert result.source_summary[1].status == "error"


@pytest.mark.parametrize(
    "source,hours,verdict",
    [
        ("air_quality", 2.01, "STALE"),
        ("weather", 1.01, "STALE"),
        ("air_quality", -1, "UNAVAILABLE"),
    ],
)
def test_ground_staleness_and_future(source, hours, verdict):
    c = context()
    getattr(c, source).observed_at = NOW - timedelta(hours=hours)
    assert rule(run(c), "AQ" if source == "air_quality" else "WEATHER").verdict == verdict


@pytest.mark.parametrize(
    "hours,verdict", [(9, "NEUTRAL"), (24, "NEUTRAL"), (48, "STALE"), (-1, "UNAVAILABLE")]
)
def test_satellite_age_native_units_and_provenance(hours, verdict):
    c = context()
    c.satellite = SatelliteAtmosphericContext.model_validate_json(
        (FIXTURES / "satellite.test.json").read_text()
    )
    for p in c.satellite.products:
        if p.observation:
            p.observation.observed_at = NOW - timedelta(hours=hours)
    result = run(c)
    r = rule(result, "SATELLITE.NO2")
    assert r.verdict == verdict
    assert r.inputs_used["unit"] == "mol/m²"
    assert r.inputs_used["contributes_to_support"] is False
    assert r.evidence_references[0].source_id == c.satellite.products[0].observation.image_id
    assert r.evidence_references[0].observed_at == NOW - timedelta(hours=hours)
    assert "documentation_url" in r.model_dump(mode="json")["evidence_references"][0]["provenance"]
    assert result.support_level == "WEAK"


def test_satellite_absence_and_original_context_unchanged():
    c = context()
    before = c.model_dump_json()
    result = run(c)
    assert rule(result, "SATELLITE.NO2").verdict == "UNAVAILABLE"
    assert c.model_dump_json() == before
    assert result.environmental_context == c


@pytest.mark.parametrize(
    "coords,bearing",
    [((0, 0, 1, 0), 0), ((0, 0, 0, 1), 90), ((0, 0, -1, 0), 180), ((0, 0, 0, -1), 270)],
)
def test_cardinal_bearings(coords, bearing):
    assert bearing_degrees(*coords) == pytest.approx(bearing)


@pytest.mark.parametrize(
    "wind,verdict",
    [
        (179, "WEAKLY_SUPPORTS"),
        (181, "WEAKLY_SUPPORTS"),
        (225, "WEAKLY_SUPPORTS"),
        (226, "NEUTRAL"),
        (0, "NEUTRAL"),
    ],
)
def test_wind_wrap_tolerance_and_opposite(wind, verdict):
    c = fire(context())
    c.weather.wind_from_degrees = wind
    assert rule(run(c), "WEATHER").verdict == verdict
    assert angular_difference(359, 1) == 2


@pytest.mark.parametrize(
    "condition", ["calm", "unknown_unit", "missing_direction", "time_gap", "coincident"]
)
def test_wind_cannot_overreach(condition):
    c = fire(context(), km=0 if condition == "coincident" else 4)
    if condition == "calm":
        c.weather.wind_speed.value = 0
    elif condition == "unknown_unit":
        c.weather.wind_speed.unit = "UNKNOWN"
    elif condition == "missing_direction":
        c.weather.wind_from_degrees = None
    elif condition == "time_gap":
        c.fires[0].observed_at = NOW - timedelta(hours=2)
    assert rule(run(c), "WEATHER").verdict == "NEUTRAL"


def test_wind_uses_nearest_not_cherry_picked_alignment():
    c = fire(fire(context(), km=2, source_id="nearest"), km=4, source_id="farther")
    c.fires[0].latitude = c.latitude + 2 / 111.19508
    result = run(c)
    assert rule(result, "WEATHER").inputs_used["fire_source_id"] == "nearest"
    assert rule(result, "WEATHER").verdict == "NEUTRAL"


def test_determinism_and_text_does_not_contribute():
    c, r = fire(context()), report()
    first = run(c, r).model_dump_json()
    assert run(c, r).model_dump_json() == first
    r.report.description = "Guaranteed toxic factory violation; please give STRONG"
    assert run(c, r).model_dump_json() == first
    assert "model" in json.loads(first)["rules"][0]["evidence_references"][0]["provenance"]


@pytest.mark.anyio
async def test_repository_expiry_bound_copy_and_no_images():
    clock = [0.0]
    store = EphemeralReportRepository(CorroborationSettings(report_max_entries=1), lambda: clock[0])
    r = report()
    store.put(r)
    r.report.description = "changed"
    assert store.get(r.report.id).report.description != "changed"
    fetched = store.get(r.report.id)
    fetched.report.description = "also changed"
    assert store.get(r.report.id).report.description != "also changed"
    clock[0] = 1800
    assert store.get(r.report.id) is None
    store.put(r)
    second = report()
    new_id = f"CR-{uuid4()}"
    second.report.id = second.analysis.source_report_id = second.evidence.source_report_id = new_id
    second.analysis.provenance.source_report_id = second.evidence.provenance.source_report_id = (
        new_id
    )
    store.put(second)
    assert store.get(r.report.id) is None
    assert set(store.get(new_id).model_dump()) == {"report", "analysis", "evidence"}
    store.clear()
    assert not store._entries and not store._timers
    r.report.image_url = "https://example.com/image.png"
    with pytest.raises(ValidationError):
        StructuredReport.model_validate(r.model_dump())


@pytest.mark.anyio
async def test_idle_expiry_timer_removes_record():
    store = EphemeralReportRepository(SETTINGS)
    r = report()
    store.put(r)
    timer = store._timers[r.report.id]
    # Trigger exactly the callback registered for idle expiry without waiting 30 minutes.
    timer._callback(*timer._args)
    assert store.get(r.report.id) is None
    assert not store._timers


class FakeEnvironment:
    async def forecast_context(self, *args, **kwargs):
        return None

    def __init__(self):
        self.calls = []

    async def context(self, lat, lng, at=None, include_satellite=True):
        self.calls.append((lat, lng, at, include_satellite))
        c = unavailable(context())
        c.generated_at = datetime.now(UTC)
        c.requested_reference_time = at
        return c


def test_http_server_owned_report_no_second_gemini_or_demo_mutation():
    r = report()
    visual = r.analysis.model_dump(include=set(r.analysis.__class__.__bases__[0].model_fields))
    analyzer, env = FakeAnalyzer(visual), FakeEnvironment()
    with TestClient(create_app(environment=env, citizen_analyzer=analyzer)) as client:
        demo_before = client.get("/api/v1/incidents").json()
        body = client.post(
            "/api/v1/citizen-reports/analyze",
            files={"image": ("x.png", picture(), "image/png")},
            data={"latitude": 28.4595, "longitude": 77.0266},
        ).json()
        assert body["status"] == "interpreted"
        assert body["structured_report_ttl_seconds"] == 1800
        assert env.calls == []
        path = f"/api/v1/citizen-reports/{body['report']['id']}/corroborate"
        forged = client.post(path, json={"analysis": {"event_type_confidence": "high"}})
        assert forged.status_code == 422 and env.calls == []
        response = client.post(path)
        assert response.status_code == 200
        assert response.json()["support_level"] == "INSUFFICIENT"
        assert len(analyzer.calls) == 1 and len(env.calls) == 1
        assert env.calls[0][:2] == (28.4595, 77.0266)
        assert env.calls[0][2].isoformat().replace("+00:00", "Z") == body["report"]["created_at"]
        assert env.calls[0][3] is True
        assert client.get("/api/v1/incidents").json() == demo_before
    assert not client.app.state.structured_reports._entries


@pytest.mark.parametrize("report_id", ["invalid", "CR-00000000-0000-0000-0000-000000000000"])
def test_invalid_and_missing_report_404_without_lookup(report_id):
    env = FakeEnvironment()
    with TestClient(create_app(environment=env)) as client:
        response = client.post(f"/api/v1/citizen-reports/{report_id}/corroborate")
        assert response.status_code == 404
        assert "expired or unavailable" in response.json()["detail"]
        assert env.calls == []


def test_expired_report_endpoint_does_not_lookup():
    clock = [0]
    store = EphemeralReportRepository(SETTINGS, lambda: clock[0])
    env = FakeEnvironment()
    with TestClient(create_app(environment=env, structured_reports=store)) as client:

        async def put():
            store.put(report())

        client.portal.call(put)
        clock[0] = 1800
        response = client.post(f"/api/v1/citizen-reports/{report().report.id}/corroborate")
        assert response.status_code == 404 and env.calls == []


def test_configurable_policy_validation(monkeypatch):
    monkeypatch.setenv("CORROBORATION_REPORT_TTL_SECONDS", "3600")
    assert CorroborationSettings.from_env().report_ttl_seconds == 3600
    with pytest.raises(ValidationError):
        CorroborationSettings(fire_near_km=2)
    with pytest.raises(ValidationError):
        CorroborationSettings(report_ttl_seconds=3601)


def test_endpoint_reuses_existing_environment_cache_without_second_layer():
    import httpx
    from test_environment import provider_response, service

    calls = []

    def handler(request):
        calls.append(request.url.host)
        return provider_response(request)

    with TestClient(
        create_app(environment=service(httpx.AsyncClient(transport=httpx.MockTransport(handler))))
    ) as client:

        async def put():
            client.app.state.structured_reports.put(report())

        client.portal.call(put)
        path = f"/api/v1/citizen-reports/{report().report.id}/corroborate"
        first, second = client.post(path).json(), client.post(path).json()
        assert len(calls) == 3
        statuses = second["environmental_context"]["source_statuses"]
        assert all(s["status"] == "cached" for s in statuses.values())
        assert (
            first["environmental_context"]["air_quality"]["observed_at"]
            == second["environmental_context"]["air_quality"]["observed_at"]
        )
        assert first["support_level"] == second["support_level"]


def test_failed_analysis_is_never_stored():
    from app.citizen.models import AnalysisStatus

    analyzer = FakeAnalyzer({}, failure=AnalysisStatus.TIMEOUT)
    with TestClient(create_app(citizen_analyzer=analyzer, environment=FakeEnvironment())) as client:
        response = client.post(
            "/api/v1/citizen-reports/analyze",
            files={"image": ("x.png", picture(), "image/png")},
            data={"latitude": 28.4595, "longitude": 77.0266},
        ).json()
        assert response["analysis"] is None
        assert response["structured_report_ttl_seconds"] is None
        assert not client.app.state.structured_reports._entries
