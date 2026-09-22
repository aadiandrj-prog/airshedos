import hashlib
import json
from pathlib import Path

import httpx
import pytest

from app.handoff.models import PollutionEvent
from scripts.demo_preflight import config_checks, inspect, provider_check
from scripts.receive_pollution_event import ReceiverError, verify_packet

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = ROOT / "docs/contracts/pollution_event_v1.schema.json"
DATA = ROOT / "apps/web/e2e/fixtures/handoff-canonical.test.json"


def verify(data):
    return verify_packet(data, hashlib.sha256(data).hexdigest(), json.loads(SCHEMA.read_text()))


def test_standalone_schema_matches_backend_and_protected_records():
    expected = PollutionEvent.model_json_schema(mode="serialization")
    expected.update(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "urn:airshedos:pollution_event_v1",
        }
    )
    assert json.loads(SCHEMA.read_text()) == expected
    for path, digest in json.loads(
        (ROOT / "docs/contracts/protected-records.json").read_text()
    ).items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path


def test_independent_receiver_accepts_existing_v1_without_app_imports():
    result = verify(DATA.read_bytes())
    assert result["status"] == "PASS" and result["simulated"]
    assert result["from"] == "HARYANA" and result["to"] == "DELHI"
    source = (ROOT / "apps/api/scripts/receive_pollution_event.py").read_text()
    assert "from app." not in source and "import app" not in source


@pytest.mark.parametrize(
    "change", ["version", "missing", "coordinate", "time", "extra", "references"]
)
def test_receiver_rejects_malformed_packets_even_with_matching_hash(change):
    packet = json.loads(DATA.read_bytes())
    if change == "version":
        packet["schema_version"] = "pollution_event_v2"
    elif change == "missing":
        del packet["destination_jurisdiction"]
    elif change == "coordinate":
        packet["location"]["latitude"] = "not a coordinate"
    elif change == "time":
        packet["created_at"] = "2026-09-22T00:00:00"  # timezone deliberately missing
    elif change == "extra":
        packet["raw_image"] = "forbidden"
    else:
        packet["origin_case_id"] = "different-case"
    with pytest.raises(ReceiverError):
        verify(json.dumps(packet).encode())


def test_receiver_requires_expected_bytes_and_rejects_duplicate_keys():
    original = DATA.read_bytes()
    with pytest.raises(ReceiverError, match="Integrity mismatch"):
        verify_packet(
            original + b" ", hashlib.sha256(original).hexdigest(), json.loads(SCHEMA.read_text())
        )
    with pytest.raises(ReceiverError, match="Duplicate"):
        verify(b'{"schema_version":"pollution_event_v1","schema_version":"pollution_event_v1"}')
    with pytest.raises(ReceiverError, match="Non-finite"):
        verify(b'{"schema_version":"pollution_event_v1","value":NaN}')
    with pytest.raises(ReceiverError, match="Non-finite"):
        verify(b'{"schema_version":"pollution_event_v1","value":1e999}')


@pytest.mark.parametrize(
    "state,expected",
    [
        ("live", "PASS"),
        ("cached", "PASS"),
        ("error", "WARN"),
        ("unavailable", "WARN"),
        ("not_configured", "WARN"),
    ],
)
def test_preflight_keeps_real_provider_states(state, expected):
    result = provider_check("source", {"status": state}, 12.3)
    assert result["result"] == expected and result["provider_status"] == state
    assert result["latency_ms"] == 12.3


def test_preflight_configuration_never_serializes_secrets():
    rows = config_checks(
        {
            "GOOGLE_CLOUD_PROJECT": "private-project",
            "NEXT_PUBLIC_GOOGLE_MAPS_BROWSER_KEY": "DO_NOT_PRINT_THIS",
        }
    )
    assert all(row["result"] == "PASS" for row in rows)
    assert "DO_NOT_PRINT_THIS" not in json.dumps(rows)
    assert "private-project" not in json.dumps(rows)
    assert all(row["result"] == "WARN" for row in config_checks({}))


@pytest.mark.anyio
async def test_preflight_health_failure_is_explicit_and_bounded():
    def handler(request):
        if request.url.path == "/ready":
            return httpx.Response(503)
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path.endswith("sources"):
            return httpx.Response(200, json={"fires": {"configured": False}})
        return httpx.Response(200, content=b"synthetic fixture or page")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        rows = await inspect(client, "http://api", "http://web", False, 28.52, 77.08)
    assert next(r for r in rows if r["check"] == "backend_ready")["result"] == "FAIL"
    assert next(r for r in rows if r["check"] == "backend_health")["result"] == "PASS"
    assert next(r for r in rows if r["check"] == "fires_configuration")["result"] == "WARN"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failed,host",
    [
        ("air_quality", "airquality.googleapis.com"),
        ("weather", "weather.googleapis.com"),
        ("fires", "firms.modaps.eosdis.nasa.gov"),
    ],
)
async def test_individual_provider_failure_drill(failed, host):
    from test_environment import LAT, LNG, provider_response, service

    def handler(request):
        return httpx.Response(503) if request.url.host == host else provider_response(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await service(client).context(LAT, LNG, include_satellite=False)
    assert getattr(result, failed) is None
    assert getattr(result.source_statuses, failed).status == "unavailable"
    for name in ("air_quality", "weather", "fires"):
        if name != failed:
            assert getattr(result.source_statuses, name).status == "live"
            assert getattr(result, name) is not None
