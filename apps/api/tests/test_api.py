from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.fixtures import load_demo_incident
from app.main import create_app
from app.models import PollutionIncident
from app.repository import IncidentRepository

INCIDENT = "/api/v1/incidents/AS-DEL-001"


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        yield client


def test_health_and_readiness(client):
    assert client.get("/health").json() == {"status": "ok"}
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "storage": "in_memory", "data_mode": "demo"}


def test_list_detail_and_provenance(client):
    response = client.get("/api/v1/incidents")
    assert response.status_code == 200
    incidents = response.json()
    assert len(incidents) == 1
    detail = client.get(INCIDENT)
    assert detail.status_code == 200
    incident = PollutionIncident.model_validate(detail.json())
    assert incident.model_dump(mode="json") == incidents[0]
    assert incident.confidence == 0.86
    assert incident.forecast.spike_probability == 0.81
    assert incident.forecast.horizon_hours == 6
    assert len(incident.evidence) == 5
    assert incident.is_demo and incident.field_verification_required
    assert incident.provenance.is_demo and incident.forecast.provenance.is_demo
    assert all(signal.provenance.is_demo for signal in incident.evidence)
    assert incident.evidence[-1].confidence is None
    assert incident.evidence[-1].observed_at is None
    assert "Field verification required" in incident.recommended_action


def test_acknowledge_updates_and_is_idempotent(client):
    first = client.post(f"{INCIDENT}/acknowledge")
    assert first.status_code == 200
    body = first.json()
    assert body["status"] == "acknowledged"
    assert len(body["actions"]) == 1
    assert body["actions"][0]["status"] == "completed"
    assert client.post(f"{INCIDENT}/acknowledge").json() == body
    assert client.get(INCIDENT).json() == body


def test_share_records_simulation_and_survives_acknowledgment(client):
    response = client.post(f"{INCIDENT}/share", json={"target_jurisdiction_id": "south-west-delhi"})
    assert response.status_code == 200
    body = response.json()
    assert body["simulated"] is True
    assert body["action"]["status"] == "simulated"
    assert body["action"]["target_jurisdiction"]["id"] == "south-west-delhi"
    assert "No notification was sent" in body["action"]["description"]
    assert client.get(INCIDENT).json() == body["incident"]
    repeat = client.post(f"{INCIDENT}/share", json={"target_jurisdiction_id": "south-west-delhi"})
    assert repeat.json() == body
    assert len(client.post(f"{INCIDENT}/acknowledge").json()["actions"]) == 2


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"target_jurisdiction_id": ""},
        {"target_jurisdiction_id": "unknown"},
        {"target_jurisdiction_id": "gurugram"},
        {"target_jurisdiction_id": "south-west-delhi", "secret": "invalid-extra-field"},
    ],
)
def test_invalid_share_does_not_mutate(client, payload):
    assert client.post(f"{INCIDENT}/share", json=payload).status_code == 422
    assert client.get(INCIDENT).json()["actions"] == []


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("get", "/api/v1/incidents/missing", None),
        ("post", "/api/v1/incidents/missing/acknowledge", None),
        ("post", "/api/v1/incidents/missing/share", {"target_jurisdiction_id": "south-west-delhi"}),
    ],
)
def test_missing_incident(client, method, path, payload):
    kwargs = {"json": payload} if payload else {}
    assert getattr(client, method)(path, **kwargs).status_code == 404


@pytest.mark.parametrize(
    "field,value",
    [
        ("confidence", 86),
        ("confidence", -0.1),
        ("confidence", float("nan")),
        ("latitude", 91),
        ("longitude", -181),
        ("detected_at", "2026-09-10T10:00:00"),
        ("updated_at", "2020-01-01T00:00:00Z"),
    ],
)
def test_schema_rejects_invalid_values(field, value):
    fixture = load_demo_incident().model_dump(mode="json")
    fixture[field] = value
    with pytest.raises(ValidationError):
        PollutionIncident.model_validate(fixture)


def test_unavailable_evidence_cannot_have_confidence():
    fixture = load_demo_incident().model_dump(mode="json")
    fixture["evidence"][-1]["confidence"] = 0.8
    with pytest.raises(ValidationError):
        PollutionIncident.model_validate(fixture)


def test_available_evidence_requires_timestamp():
    fixture = load_demo_incident().model_dump(mode="json")
    fixture["evidence"][0]["observed_at"] = None
    with pytest.raises(ValidationError):
        PollutionIncident.model_validate(fixture)


def test_repository_isolation_and_concurrent_acknowledgment():
    repository = IncidentRepository()
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(repository.acknowledge, ["AS-DEL-001"] * 12))
    incident = repository.get("AS-DEL-001")
    assert len(incident.actions) == 1
    incident.actions.clear()
    assert len(repository.get("AS-DEL-001").actions) == 1
    assert IncidentRepository().get("AS-DEL-001").actions == []


def test_cors_limits_browser_origins(client):
    headers = {"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"}
    response = client.options(f"{INCIDENT}/acknowledge", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    headers["Origin"] = "https://airshedos.vercel.app"
    response = client.options(f"{INCIDENT}/acknowledge", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == headers["Origin"]
    headers["Origin"] = "https://unrelated.example"
    assert client.options(f"{INCIDENT}/acknowledge", headers=headers).status_code == 400


def test_openapi_contains_domain_contract(client):
    schema = client.get("/openapi.json").json()
    for name in [
        "CitizenReport",
        "EvidenceSignal",
        "PollutionIncident",
        "ForecastRisk",
        "Jurisdiction",
        "IncidentAction",
        "ShareRequest",
        "ShareResponse",
    ]:
        assert name in schema["components"]["schemas"]
