import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_corroboration import FakeEnvironment, report
from test_review import evidence

from app.handoff.models import (
    TRANSITIONS,
    CreateHandoff,
    HandoffState,
    PollutionEvent,
    TransitionHandoff,
)
from app.handoff.packet import canonical_bytes, payload_hash
from app.handoff.repository import HandoffConflict, HandoffRepository
from app.main import create_app
from app.review.models import ReviewRequest
from app.review.repository import OfficerCaseRepository


def request(**updates):
    return CreateHandoff(
        **{
            "origin_jurisdiction": "HARYANA",
            "destination_jurisdiction": "DELHI",
            "reason": "CROSS_BORDER_EVENT",
            "expected_case_revision": 1,
            **updates,
        }
    )


def case():
    cases = OfficerCaseRepository()
    record, assessment = evidence()
    # Free-form citizen text must not leak into the interoperability payload.
    record.report.description = "PRIVATE_CITIZEN_TEXT data:image/png;base64,excluded"
    record.report.is_synthetic = True
    item = cases.add(record, assessment, 60)
    item = cases.transition(item.id, ReviewRequest(state="UNDER_REVIEW", expected_revision=0))
    cases.clear()
    return item


def step(store, record, state):
    return store.transition(
        record.id, TransitionHandoff(state=state, expected_revision=record.revision)
    )


def received(store):
    item = store.create(case(), request())
    for state in ["READY", "SENT_SIMULATED", "RECEIVED"]:
        item = step(store, item, state)
    return item


@pytest.mark.anyio
async def test_packet_allowlist_provenance_units_temporal_and_export_roundtrip():
    store = HandoffRepository()
    source = case()
    original = source.model_dump_json()
    item = store.create(source, request())
    packet = item.payload
    assert packet.schema_version == "pollution_event_v1"
    assert packet.review_state == "UNDER_REVIEW"
    assert packet.evidence.gemini == source.snapshot.record.analysis
    assert packet.forecast.summaries == source.snapshot.assessment.forecast_outlook.summaries
    assert (
        packet.forecast.hourly_forecasts
        == source.snapshot.assessment.forecast_outlook.hourly_forecasts
    )
    assert packet.temporal.report_submitted_at == source.snapshot.record.report.created_at
    assert packet.temporal.image_capture_time is None
    assert (
        packet.evidence.air_quality == source.snapshot.assessment.environmental_context.air_quality
    )
    assert packet.evidence.fires == source.snapshot.assessment.environmental_context.fires
    data, digest, event_id, version = store.export(item.id)
    assert digest == payload_hash(data) == item.payload_hash
    assert data == canonical_bytes(PollutionEvent.model_validate_json(data))
    assert event_id == packet.event_id and version == packet.event_version
    assert (
        b"PRIVATE_CITIZEN_TEXT" not in data and b"base64" not in data and b"image_url" not in data
    )
    assert b"inputs_used" not in data and b"configured" not in data and b"latency_ms" not in data
    assert not data.endswith(b"\n")
    assert source.model_dump_json() == original
    assert (
        packet.evidence.rules[0].evidence_references
        == source.snapshot.assessment.rules[0].evidence_references
    )
    store.clear()


@pytest.mark.anyio
async def test_explicit_schema_version_and_structural_validation():
    store = HandoffRepository()
    event = store.create(case(), request()).payload.model_dump(mode="json")
    for mutate in [
        lambda p: p.pop("schema_version"),
        lambda p: p.update(schema_version="pollution_event_v2"),
        lambda p: p.update(event_version=0),
        lambda p: p.update(event_version=True),
        lambda p: p.update(location={"latitude": 91, "longitude": 0}),
        lambda p: p.update(raw_media="data:image/png;base64,AAA"),
        lambda p: p.update(destination_jurisdiction="CPCB"),
        lambda p: p.update(origin_case_id="mismatch"),
        lambda p: p.update(image_bytes="forbidden"),
        lambda p: p.update(updated_at="2026-01-01T00:00:00Z"),
    ]:
        payload = json.loads(json.dumps(event))
        mutate(payload)
        with pytest.raises(ValidationError):
            PollutionEvent.model_validate(payload)
    # Dict order and escaping in input do not affect the normalized canonical encoding.
    reversed_keys = dict(reversed(list(event.items())))
    assert canonical_bytes(PollutionEvent.model_validate(event)) == canonical_bytes(
        PollutionEvent.model_validate(reversed_keys)
    )
    store.clear()


@pytest.mark.anyio
async def test_versioning_freezes_review_forecast_and_evidence():
    store = HandoffRepository()
    source = case()
    first = store.create(source, request())
    before = store.export(first.id)[0]
    source.review.state = "MONITORING"
    source.review.revision = 2
    second = store.create(source, request(expected_case_revision=2))
    assert second.event_version > first.event_version
    assert second.event_id == first.event_id and second.id != first.id
    assert (
        first.payload.review_state == "UNDER_REVIEW" and second.payload.review_state == "MONITORING"
    )
    first.payload.forecast.summaries[0].max_pm25.value = 999
    assert store.export(first.id)[0] == before
    assert (
        store.get(first.id).payload.forecast.summaries
        == source.snapshot.assessment.forecast_outlook.summaries
    )
    store.clear()


@pytest.mark.anyio
@pytest.mark.parametrize("outcome", ["ACCEPTED", "REJECTED", "RETURNED_FOR_REVIEW"])
async def test_complete_lifecycle_append_only_audit_and_retry(outcome):
    store = HandoffRepository()
    item = received(store)
    original_audit = [a.model_dump() for a in item.audit]
    frozen = store.export(item.id)[0]
    item = step(store, item, outcome)
    assert [a.model_dump() for a in item.audit[:4]] == original_audit
    assert item.audit[-1].actor == "destination_control_room"
    assert item.audit[-1].payload_hash == payload_hash(frozen)
    if outcome == "RETURNED_FOR_REVIEW":
        for state in ["READY", "SENT_SIMULATED", "RECEIVED", "ACCEPTED"]:
            item = step(store, item, state)
        assert len(item.audit) == 9
    assert store.export(item.id)[0] == frozen
    assert [a.sequence for a in item.audit] == list(range(len(item.audit)))
    item.audit[0].payload_hash = "mutated outside store"
    assert store.get(item.id).audit[0].payload_hash == payload_hash(frozen)
    store.clear()


@pytest.mark.anyio
@pytest.mark.parametrize("before", list(HandoffState))
@pytest.mark.parametrize("after", list(HandoffState))
async def test_transition_matrix(before, after):
    store = HandoffRepository()
    item = store.create(case(), request())
    paths = {
        "DRAFT": [],
        "READY": ["READY"],
        "SENT_SIMULATED": ["READY", "SENT_SIMULATED"],
        "RECEIVED": ["READY", "SENT_SIMULATED", "RECEIVED"],
        "ACCEPTED": ["READY", "SENT_SIMULATED", "RECEIVED", "ACCEPTED"],
        "REJECTED": ["READY", "SENT_SIMULATED", "RECEIVED", "REJECTED"],
        "RETURNED_FOR_REVIEW": ["READY", "SENT_SIMULATED", "RECEIVED", "RETURNED_FOR_REVIEW"],
    }
    for state in paths[before]:
        item = step(store, item, state)
    if after in TRANSITIONS[before]:
        assert step(store, item, after).state == after
    else:
        with pytest.raises(HandoffConflict):
            step(store, item, after)
        assert store.get(item.id) == item
    store.clear()


@pytest.mark.anyio
async def test_integrity_mismatch_blocks_acceptance_and_export():
    store = HandoffRepository()
    item = received(store)
    store._entries[item.id].data += b" "  # Even semantically harmless byte changes must fail.
    assert store.get(item.id).integrity == "MISMATCH"
    original = store.get(item.id)
    with pytest.raises(HandoffConflict, match="Integrity"):
        step(store, item, "ACCEPTED")
    with pytest.raises(HandoffConflict, match="Integrity"):
        store.export(item.id)
    assert store.get(item.id) == original
    store.clear()


@pytest.mark.anyio
async def test_revision_conflicts_review_gate_and_supported_jurisdictions():
    store = HandoffRepository()
    source = case()
    with pytest.raises(HandoffConflict, match="review changed"):
        store.create(source, request(expected_case_revision=0))
    source.review.state = "NEW"
    with pytest.raises(HandoffConflict, match="Begin"):
        store.create(source, request())
    source.review.state = "CLOSED_NO_ACTION"
    with pytest.raises(HandoffConflict):
        store.create(source, request())
    for fields in [
        {"origin_jurisdiction": "Unknown"},
        {"destination_jurisdiction": "PUNJAB"},
        {"destination_jurisdiction": "HARYANA"},
        {"reason": "model_says_send"},
    ]:
        with pytest.raises(ValidationError):
            request(**fields)
    item = store.create(case(), request(destination_jurisdiction="UTTAR_PRADESH"))
    with pytest.raises(HandoffConflict, match="changed"):
        store.transition(item.id, TransitionHandoff(state="READY", expected_revision=2))
    assert store.get(item.id) == item
    store.clear()


@pytest.mark.anyio
async def test_partial_data_and_unknown_location_jurisdiction_do_not_block():
    source = case()
    source.snapshot.jurisdiction.state = "Unknown"
    source.snapshot.assessment.environmental_context.fires = None
    source.snapshot.assessment.environmental_context.satellite = None
    source.snapshot.assessment.forecast_outlook = None
    store = HandoffRepository()
    item = store.create(source, request())
    assert item.payload.forecast is None and item.payload.evidence.fires is None
    assert item.payload.location.jurisdiction_at_location.state == "Unknown"
    assert step(store, item, "READY").state == "READY"
    store.clear()


@pytest.mark.anyio
async def test_case_expiry_independent_handoff_expiry_capacity_and_ordering():
    clock = [0.0]
    now = datetime(2026, 9, 22, tzinfo=UTC)
    cases = OfficerCaseRepository(clock=lambda: clock[0])
    source = cases.add(*evidence(), 5)
    source = cases.transition(source.id, ReviewRequest(state="UNDER_REVIEW", expected_revision=0))
    store = HandoffRepository(
        max_entries=2,
        ttl_seconds=10,
        clock=lambda: clock[0],
        utc_clock=lambda: now + timedelta(seconds=clock[0]),
    )
    first = store.create(source, request())
    assert not store.summaries(destination="DELHI")
    first = step(store, step(store, first, "READY"), "SENT_SIMULATED")
    clock[0] = 6
    assert cases.get(source.id) is None
    assert step(store, first, "RECEIVED").integrity == "VERIFIED"
    second = store.create(source, request())
    second = step(store, step(store, second, "READY"), "SENT_SIMULATED")
    assert [i.id for i in store.summaries(destination="DELHI")] == [second.id, first.id]
    third = store.create(source, request(destination_jurisdiction="UTTAR_PRADESH"))
    with pytest.raises(KeyError):
        store.get(first.id)
    assert third.event_version > second.event_version
    clock[0] = 16
    assert store.summaries() == [] and not store._timers
    cases.clear()
    store.clear()


@pytest.mark.anyio
async def test_idle_expiry_and_bounded_audit():
    store = HandoffRepository()
    item = received(store)
    while len(item.audit) < 125:
        for state in ["RETURNED_FOR_REVIEW", "READY", "SENT_SIMULATED", "RECEIVED"]:
            if len(item.audit) == 128:
                break
            item = step(store, item, state)
    with pytest.raises(HandoffConflict, match="capacity"):
        step(store, item, item.allowed_transitions[0])
    timer = store._timers[item.id]
    timer._callback(*timer._args)
    with pytest.raises(KeyError):
        store.get(item.id)
    assert not store._timers


def test_http_handoff_export_and_no_provider_reruns(monkeypatch):
    environment = FakeEnvironment()
    with TestClient(create_app(environment=environment)) as client:
        source = report()
        client.portal.call(client.app.state.structured_reports.put, source)
        assessment = client.post(f"/api/v1/citizen-reports/{source.report.id}/corroborate").json()
        case_id = assessment["id"]
        base = f"/api/v1/review/cases/{case_id}"
        client.post(base + "/review", json={"state": "UNDER_REVIEW", "expected_revision": 0})
        before = client.get(base).json()

        async def forbidden(*args, **kwargs):
            raise AssertionError("Handoff must not rerun any provider or Gemini")

        monkeypatch.setattr(environment, "context", forbidden)
        monkeypatch.setattr(environment, "forecast_context", forbidden)
        monkeypatch.setattr(client.app.state.citizen_analyzer, "analyze", forbidden)
        response = client.post(base + "/handoffs", json=request().model_dump())
        assert response.status_code == 201
        item = response.json()
        frozen = client.get(f"/api/v1/handoffs/{item['id']}/export")
        assert frozen.headers["x-payload-sha256"] == payload_hash(frozen.content)
        for state in ["READY", "SENT_SIMULATED", "RECEIVED", "ACCEPTED"]:
            response = client.post(
                f"/api/v1/handoffs/{item['id']}/transition",
                json={"state": state, "expected_revision": item["revision"]},
            )
            assert response.status_code == 200
            item = response.json()
        assert client.get(base).json() == before
        assert len(environment.calls) == 1
        assert client.get(f"/api/v1/handoffs/{item['id']}/export").content == frozen.content
        assert len(client.get("/api/v1/handoffs?destination=DELHI").json()) == 1
        assert client.get("/api/v1/handoffs?destination=PUNJAB").status_code == 422
        assert (
            client.post(
                f"/api/v1/handoffs/{item['id']}/transition",
                json={"state": "READY", "expected_revision": 0},
            ).status_code
            == 409
        )
        assert (
            client.post(
                base + "/handoffs", json={**request().model_dump(), "image": "forbidden"}
            ).status_code
            == 422
        )
        client.portal.call(client.app.state.officer_cases.clear)
        assert client.get(f"/api/v1/handoffs/{item['id']}").status_code == 200
        assert client.post(base + "/handoffs", json=request().model_dump()).status_code == 404
        client.portal.call(client.app.state.handoffs.clear)
        assert client.get(f"/api/v1/handoffs/{item['id']}").status_code == 404
        assert client.get(f"/api/v1/handoffs/{item['id']}/export").status_code == 404
