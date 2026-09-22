from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from test_corroboration import SETTINGS, FakeEnvironment, context, report

from app.corroboration.engine import assess
from app.main import create_app
from app.review.jurisdiction import resolve_jurisdiction
from app.review.models import ReviewRequest
from app.review.repository import OfficerCaseRepository, ReviewConflict


@pytest.mark.parametrize(
    "lat,lng,state",
    [
        (28.4595, 77.0266, "Haryana"),
        (28.6139, 77.209, "Delhi"),
        (28.5355, 77.391, "Uttar Pradesh"),
        (0, 0, "Unknown"),
        (28.53, 77.02, "Unknown"),
        (28.55, 77.29, "Unknown"),
    ],
)
def test_prototype_jurisdiction(lat, lng, state):
    result = resolve_jurisdiction(lat, lng)
    assert result.state == state and not result.authoritative
    assert "not an official" in result.note and "No authority routing" in result.note


def test_overlapping_prototype_configuration_is_unknown(monkeypatch):
    from app.review import jurisdiction

    monkeypatch.setattr(jurisdiction, "AREAS", [jurisdiction.AREAS[0], jurisdiction.AREAS[0]])
    assert resolve_jurisdiction(28.4595, 77.0266).state == "Unknown"


def evidence():
    record = report()
    assessment = assess(record, context(), SETTINGS)
    # Preserve a real-shaped forecast in the immutable snapshot as well.
    import json
    from pathlib import Path

    from app.environment.forecast_models import AirQualityForecastContext

    assessment.forecast_outlook = AirQualityForecastContext.model_validate(
        json.loads((Path(__file__).parents[2] / "web/e2e/fixtures/forecast.test.json").read_text())
    )
    return record, assessment


@pytest.mark.anyio
async def test_lifecycle_snapshot_immutability_revision_and_no_expiry_extension():
    now = datetime.now(UTC)
    store = OfficerCaseRepository(utc_clock=lambda: now)
    record, assessment = evidence()
    case = store.add(record, assessment, 60)
    frozen = case.snapshot.model_dump_json()
    expires = case.expires_at
    assert case.review.state == "NEW" and case.review.action_at is None
    for revision, state in enumerate(
        ["UNDER_REVIEW", "ACKNOWLEDGED", "MONITORING", "UNDER_REVIEW", "CLOSED_NO_ACTION"]
    ):
        case = store.transition(case.id, ReviewRequest(state=state, expected_revision=revision))
        assert case.snapshot.model_dump_json() == frozen
        assert case.review.revision == revision + 1 and case.review.action_at == now
        assert case.expires_at == expires
    with pytest.raises(ReviewConflict):
        store.transition(case.id, ReviewRequest(state="UNDER_REVIEW", expected_revision=5))
    assert store.get(case.id).review.state == "CLOSED_NO_ACTION"
    store.clear()


@pytest.mark.anyio
async def test_invalid_transition_and_stale_revision_do_not_mutate():
    store = OfficerCaseRepository()
    case = store.add(*evidence(), 60)
    for target, revision in [
        ("ACKNOWLEDGED", 0),
        ("MONITORING", 0),
        ("CLOSED_NO_ACTION", 0),
        ("UNDER_REVIEW", 99),
    ]:
        with pytest.raises(ReviewConflict):
            store.transition(case.id, ReviewRequest(state=target, expected_revision=revision))
        assert store.get(case.id) == case
    store.clear()


@pytest.mark.anyio
async def test_copies_duplicate_add_and_ttl_expiry():
    clock = [0.0]
    store = OfficerCaseRepository(clock=lambda: clock[0])
    record, assessment = evidence()
    case = store.add(record, assessment, 60)
    digest = case.snapshot.evidence_sha256
    record.report.description = "mutated outside repository"
    assessment.forecast_outlook.summaries[0].max_pm25.value = 999
    case.snapshot.assessment.support_level = "STRONG"
    assert store.get(case.id).snapshot.evidence_sha256 == digest
    assert store.get(case.id).snapshot.record.report.description != record.report.description
    assert (
        store.get(case.id).snapshot.assessment.forecast_outlook.summaries[0].max_pm25.value != 999
    )
    store.transition(case.id, ReviewRequest(state="UNDER_REVIEW", expected_revision=0))
    assert store.add(record, assessment, 3600).review.state == "UNDER_REVIEW"
    clock[0] = 60
    assert store.get(case.id) is None and not store._timers
    with pytest.raises(KeyError):
        store.transition(case.id, ReviewRequest(state="MONITORING", expected_revision=1))
    assert store.add(record, assessment, 0) is None


@pytest.mark.anyio
async def test_idle_expiry_capacity_and_queue_order():
    store = OfficerCaseRepository(max_entries=5)
    cases = []
    for i in range(6):
        record, assessment = evidence()
        record.report.created_at += timedelta(minutes=i)
        assessment.id = f"CA-{i}"
        cases.append(store.add(record, assessment, 60))
    assert store.get("CA-0") is None
    for case_id, state in [
        ("CA-5", "CLOSED_NO_ACTION"),
        ("CA-4", "ACKNOWLEDGED"),
        ("CA-3", "MONITORING"),
    ]:
        store.transition(case_id, ReviewRequest(state="UNDER_REVIEW", expected_revision=0))
        store.transition(case_id, ReviewRequest(state=state, expected_revision=1))
    store.transition("CA-2", ReviewRequest(state="UNDER_REVIEW", expected_revision=0))
    assert [c.id for c in store.summaries()] == ["CA-1", "CA-2", "CA-4", "CA-3", "CA-5"]
    timer = store._timers["CA-1"]
    timer._callback(*timer._args)
    assert store.get("CA-1") is None
    store.clear()
    assert not store._entries and not store._timers


def test_case_http_workflow_only_no_provider_reruns_or_evidence_writes():
    env = FakeEnvironment()
    record = report()
    with TestClient(create_app(environment=env)) as client:

        async def insert():
            client.app.state.structured_reports.put(record)

        client.portal.call(insert)
        result = client.post(f"/api/v1/citizen-reports/{record.report.id}/corroborate")
        assert result.status_code == 200
        case_id = result.json()["id"]
        queue = client.get("/api/v1/review/cases").json()
        assert len(queue) == 1 and queue[0]["id"] == case_id
        before = client.get(f"/api/v1/review/cases/{case_id}").json()
        assert before["snapshot"]["assessment"] == result.json()
        assert before["snapshot"]["record"]["report"]["image_url"] is None
        result = client.post(
            f"/api/v1/review/cases/{case_id}/review",
            json={"state": "UNDER_REVIEW", "expected_revision": 0},
        )
        assert result.status_code == 200
        after = result.json()
        assert after["snapshot"] == before["snapshot"]
        assert (
            after["review"]["state"] == "UNDER_REVIEW"
            and after["storage"] == "ephemeral_process_local"
        )
        assert len(env.calls) == 1
        assert (
            client.post(
                f"/api/v1/review/cases/{case_id}/review",
                json={"state": "MONITORING", "expected_revision": 0},
            ).status_code
            == 409
        )
        assert (
            client.post(
                f"/api/v1/review/cases/{case_id}/review",
                json={"state": "MONITORING", "expected_revision": 1, "snapshot": {}},
            ).status_code
            == 422
        )
        assert (
            client.post(
                f"/api/v1/review/cases/{case_id}/review",
                json={"state": "ENFORCEMENT", "expected_revision": 1},
            ).status_code
            == 422
        )
        assert client.get("/api/v1/review/cases/missing").status_code == 404
        client.portal.call(client.app.state.officer_cases.clear)
        assert client.get(f"/api/v1/review/cases/{case_id}").status_code == 404
        assert client.get("/api/v1/review/cases").json() == []
    assert not client.app.state.officer_cases._entries


@pytest.mark.anyio
async def test_case_cannot_outlive_original_report():
    from app.corroboration.repository import EphemeralReportRepository

    clock = [0.0]
    reports = EphemeralReportRepository(SETTINGS, clock=lambda: clock[0])
    cases = OfficerCaseRepository(clock=lambda: clock[0])
    record, assessment = evidence()
    reports.put(record)
    clock[0] = 1790
    cases.add(record, assessment, reports.remaining_ttl(record.report.id))
    clock[0] = 1800
    assert cases.get(assessment.id) is None and reports.get(record.report.id) is None
    reports.clear()
