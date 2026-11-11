"""Operational readiness and route-surface inventory, with actual PostgreSQL scope."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_access import access_fixture as access_fixture
from test_access import fixture as fixture
from test_access import persistence_fixture as persistence_fixture
from test_access import pg as pg
from test_access import signing_key as signing_key
from test_persistence import RESIDENT

from app.main import create_app
from app.operations.readiness import pulse
from app.persistence.models import MaintenanceHeartbeat, RecoveryControl, WorkerHeartbeat
from app.persistence.retention import RetentionService


def released(f):
    epoch = uuid4()
    with f["sessions"].begin() as session:
        row = session.get(RecoveryControl, "pilot")
        row.epoch, row.state = epoch, "READY"
    f["repo"].release_epoch = epoch
    pulse(f["repo"], "processing")
    RetentionService(f["repo"], f["store"]).sweep()
    return epoch


def test_required_readiness_optional_degradation_and_stale_worker(access_fixture):
    f = access_fixture
    assert f["client"].get("/ready").status_code == 503
    released(f)
    ready = f["client"].get("/ready")
    assert ready.status_code == 200, ready.text
    assert ready.json()["capabilities"]["gemini"] == "unavailable"
    assert ready.json()["checks"]["identity"] == "configured_not_live_verified"
    assert ready.json()["checks"]["cleanup"] == "ready"
    assert f["client"].get("/health").json() == {"status": "ok"}
    with f["sessions"].begin() as session:
        session.get(WorkerHeartbeat, "processing").succeeded_at = datetime.now(UTC) - timedelta(
            seconds=46
        )
    assert f["client"].get("/ready").status_code == 503
    # Processing outage never prevents an authenticated user viewing an accepted report.
    own = f["client"].get(
        f"/api/v2/resident/reports/{f['a'].report_id}", headers=f["headers"][RESIDENT.subject]
    )
    assert own.status_code == 200
    pulse(f["repo"], "processing")
    with f["sessions"].begin() as session:
        session.get(MaintenanceHeartbeat, "retention").succeeded_at = datetime.now(UTC) - timedelta(
            seconds=121
        )
    assert f["client"].get("/ready").status_code == 503


def test_quarantine_blocks_valid_bound_sessions_and_worker(access_fixture):
    from app.persistence.contracts import PersistenceError
    from app.processing.queue import DurableQueue

    f = access_fixture
    released(f)
    with f["sessions"].begin() as session:
        session.get(RecoveryControl, "pilot").state = "QUARANTINED"
    own = f["client"].get(
        f"/api/v2/resident/reports/{f['a'].report_id}", headers=f["headers"][RESIDENT.subject]
    )
    assert own.status_code == 503
    with pytest.raises(PersistenceError):
        DurableQueue(f["repo"]).claim()
    assert f["client"].get("/ready").status_code == 503
    assert str(f["repo"].release_epoch) not in f["client"].get("/ready").text


def test_explicit_text_only_readiness_does_not_claim_media(access_fixture, monkeypatch):
    f = access_fixture
    released(f)
    f["service"].media = None
    assert f["client"].get("/ready").status_code == 503
    monkeypatch.setenv("PILOT_MEDIA_REQUIRED", "0")
    response = f["client"].get("/ready")
    assert response.status_code == 200
    assert response.json()["capabilities"]["private_images"] == "unavailable_text_only"


@pytest.mark.parametrize(
    "key",
    [
        "DATABASE_URL",
        "SESSION_DATABASE_URL",
        "S3_ACCESS_KEY_ID",
        "GOOGLE_CLOUD_PROJECT",
        "NASA_FIRMS_MAP_KEY",
    ],
)
def test_demo_rejects_private_or_paid_runtime_configuration(monkeypatch, key):
    monkeypatch.setenv(key, "synthetic-never-a-credential")
    with pytest.raises(ValueError):
        create_app(mode="prototype")


def test_all_protected_and_legacy_route_surfaces_fail_closed_anonymously(access_fixture):
    f = access_fixture
    checked = []
    for path, operations in f["client"].app.openapi()["paths"].items():
        if not path.startswith("/api/"):
            continue
        for param in (
            "report_id",
            "receipt_id",
            "case_id",
            "unit_id",
            "version_id",
            "media_id",
            "request_id",
            "membership_id",
            "proposal_id",
            "task_id",
            "key",
        ):
            path = path.replace("{" + param + "}", str(uuid4()))
        # All remaining prototype path placeholders are opaque untrusted IDs.
        import re

        path = re.sub(r"\{[^}]+\}", str(uuid4()), path)
        for method in sorted(
            m.upper() for m in operations if m in {"get", "post", "put", "delete", "patch"}
        ):
            response = f["client"].request(method, path, json={} if method == "POST" else None)
            expected = (
                (200 if path == "/api/v2/explore/areas" else 404)
                if path.startswith("/api/v2/explore/")
                else (404 if path.startswith("/api/v1") else 401)
            )
            assert response.status_code == expected, (
                path,
                method,
                response.text,
            )
            assert response.headers["cache-control"] == "private, no-store"
            checked.append((method, path))
    assert len(checked) >= 40


def test_withdrawal_stops_private_media_reads_and_projection(access_fixture):
    from test_persistence import REVIEWER

    from app.persistence.models import Report

    f = access_fixture
    with f["sessions"].begin() as session:
        session.get(Report, f["a"].report_id).withdrawn_at = datetime.now(UTC)
    own = f["client"].get(
        f"/api/v2/resident/reports/{f['a'].report_id}", headers=f["headers"][RESIDENT.subject]
    )
    assert own.status_code == 200 and own.json()["media"] is None
    for path, subject in (
        (f"/api/v2/resident/media/{f['media_a']}", RESIDENT.subject),
        (
            f"/api/v2/authority/units/{f['unit']}/cases/{f['a'].case_id}/media/{f['media_a']}",
            REVIEWER.subject,
        ),
    ):
        assert f["client"].get(path, headers=f["headers"][subject]).status_code == 404


def test_readiness_requires_an_approved_triage_unit_and_current_reviewer(access_fixture):
    from app.persistence.models import Membership

    f = access_fixture
    released(f)
    f["repo"].triage_unit_id = None
    assert f["client"].get("/ready").status_code == 503
    f["repo"].triage_unit_id = f["unit"]
    with f["sessions"].begin() as session:
        for membership in session.scalars(
            select(Membership).where(Membership.unit_id == f["unit"])
        ):
            membership.state = "SUSPENDED"
    response = f["client"].get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["triage"] == "approved_unit_and_reviewer_required"


def test_resident_paid_context_requires_owned_routed_case_and_quota(access_fixture):
    from sqlalchemy import func

    from app.persistence.models import Case, EvidenceVersion, Report

    f = access_fixture

    class Source:
        configured = True
        name = "synthetic_current_aq"

        def __init__(self):
            self.calls = []

        async def fetch(self, lat, lng):
            self.calls.append((lat, lng))
            return None

    source = Source()
    f["client"].app.state.environment.providers["air_quality"] = source
    body = {"report_id": str(f["a"].report_id)}

    def request(data):
        return f["client"].post(
            "/api/v2/resident/context", json=data, headers=f["headers"][RESIDENT.subject]
        )

    assert request({"latitude": 28.5, "longitude": 77.1}).status_code == 422
    assert request({"report_id": str(f["b"].report_id)}).status_code == 404
    assert request({"report_id": str(uuid4())}).status_code == 404
    assert (
        request(body | {"latitude": 0, "longitude": 0, "unit_id": str(f["unit"])}).status_code
        == 422
    )
    f["repo"].limits = f["repo"].limits.model_copy(update={"provider_calls_per_day": 0})
    assert request(body).status_code == 429
    assert source.calls == []
    f["repo"].limits = f["repo"].limits.model_copy(update={"provider_calls_per_day": 100})
    with f["sessions"].begin() as session:
        session.get(Case, f["a"].case_id).assigned_unit_id = None
    assert request(body).status_code == 404
    with f["sessions"].begin() as session:
        session.get(Case, f["a"].case_id).assigned_unit_id = f["unit"]
        session.get(Report, f["a"].report_id).withdrawn_at = datetime.now(UTC)
    assert request(body).status_code == 410
    assert source.calls == []
    with f["sessions"].begin() as session:
        session.get(Report, f["a"].report_id).withdrawn_at = None
    result = request(body)
    assert result.status_code == 200, result.text
    assert source.calls == [(28.5, 77.1)]
    assert result.headers["cache-control"] == "private, no-store"
    with f["sessions"]() as session:
        assert session.scalar(select(func.count()).select_from(EvidenceVersion)) == 0


def test_resident_context_rechecks_withdrawal_after_provider_io(access_fixture):
    from app.persistence.models import Report

    f = access_fixture

    class WithdrawingSource:
        configured = True
        name = "synthetic_withdraw_during_lookup"

        async def fetch(self, *_args):
            with f["sessions"].begin() as session:
                session.get(Report, f["a"].report_id).withdrawn_at = datetime.now(UTC)
            return None

    f["client"].app.state.environment.providers["air_quality"] = WithdrawingSource()
    response = f["client"].post(
        "/api/v2/resident/context",
        json={"report_id": str(f["a"].report_id)},
        headers=f["headers"][RESIDENT.subject],
    )
    assert response.status_code == 410
