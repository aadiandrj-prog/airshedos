"""Phase 4 boundaries and two-sided review using real PostgreSQL and signed principals."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from test_access import access_fixture as access_fixture
from test_access import fixture as fixture
from test_access import persistence_fixture as persistence_fixture
from test_access import pg as pg
from test_access import signing_key as signing_key
from test_citizen import FakeAnalyzer
from test_citizen import output as output
from test_persistence import RESIDENT, REVIEWER

from app.citizen.models import AnalysisStatus
from app.citizen.settings import CitizenSettings
from app.persistence.models import (
    Case,
    EvidenceFragment,
    EvidenceVersion,
    Membership,
    Report,
    ReviewEvent,
)
from app.persistence.retention import RetentionService


def base(f, case=None, unit=None):
    return f"/api/v2/authority/units/{unit or f['unit']}/cases/{case or f['a'].case_id}"


def detail(f, actor=REVIEWER.subject, **kw):
    return f["client"].get(base(f, **kw), headers=f["headers"][actor])


def act(f, path, body, actor=REVIEWER.subject, revision=None, **kw):
    if revision is None:
        current = detail(f, actor, **kw)
        assert current.status_code == 200, current.text
        revision = current.json()["revision"]
    return f["client"].post(
        base(f, **kw) + "/" + path,
        headers=f["headers"][actor],
        json={"expected_revision": revision, **body},
    )


def finish_refresh(f, response):
    """HTTP enqueues only; explicitly drive the real worker in this synthetic test."""
    import asyncio
    from datetime import UTC, datetime

    from app.persistence.models import Job
    from app.processing.queue import DurableQueue
    from app.processing.worker import ProcessingWorker

    f["repo"].clock = lambda: datetime.now(UTC)
    assert response.status_code == 202, response.text
    request_id = UUID(response.json()["request_id"])
    app = f["client"].app
    queue = DurableQueue(f["repo"], backoff=(0, 0))
    worker = ProcessingWorker(
        f["repo"],
        app.state.environment,
        app.state.citizen_analyzer,
        app.state.corroboration_settings,
        store=f["store"],
        queue=queue,
    )
    with f["sessions"]() as session:
        report_id = session.scalar(select(Job.report_id).where(Job.request_id == request_id))
    for _ in range(3):
        lease = queue.claim(report_id=report_id)
        if lease:
            asyncio.run(worker.execute(lease))
    with f["sessions"]() as session:
        job = session.scalar(select(Job).where(Job.request_id == request_id))
        version = session.scalar(
            select(EvidenceVersion.id).where(EvidenceVersion.request_id == request_id)
        )
        return dict(
            request_id=str(request_id),
            state=job.state,
            safe_reason=job.safe_reason,
            version_id=str(version) if version else None,
        )


def cancel_initial(f):
    """Phase 4 manual-pipeline fixtures start after initial intake processing was cancelled."""
    from app.persistence.models import Job

    with f["sessions"].begin() as session:
        session.execute(update(Job).where(Job.kind == "PROCESS_REPORT").values(state="CANCELLED"))


def test_complete_human_round_trip_publication_closure_reopen_and_packet(access_fixture):
    f = access_fixture
    assert act(f, "assignments", {"claim_self": True}).status_code == 200
    assert (
        act(
            f, "review-events", {"state": "UNDER_REVIEW", "reason": "Synthetic assessment started."}
        ).status_code
        == 200
    )
    assert act(f, "internal-notes", {"body": "PRIVATE PHASE4 NOTE"}).status_code == 200
    resident = (
        f["client"]
        .get(f"/api/v2/resident/reports/{f['a'].report_id}", headers=f["headers"][RESIDENT.subject])
        .json()
    )
    assert resident["reporter_status"] == "RECEIVED" and "PRIVATE PHASE4 NOTE" not in json.dumps(
        resident
    )
    assert (
        act(f, "information-requests", {"prompt": "Is the activity still ongoing?"}).status_code
        == 200
    )
    request = detail(f).json()["information_requests"][0]
    response = f["client"].post(
        f"/api/v2/resident/reports/{f['a'].report_id}/information-requests/{request['id']}/replies",
        headers=f["headers"][RESIDENT.subject]
        | {
            "Idempotency-Key": str(uuid4()),
            "Idempotency-Key-Created-At": f["clock"][0].isoformat(),
        },
        json={"body": "SYNTHETIC RESIDENT REPLY: no longer observed."},
    )
    assert response.status_code == 201
    assert detail(f).json()["supplements"][0]["body"].startswith("SYNTHETIC RESIDENT REPLY")
    assert (
        act(
            f, "field-follow-ups", {"reason": "Check the declared location; no agency dispatch."}
        ).status_code
        == 200
    )
    task = detail(f).json()["field_follow_ups"][0]
    assert (
        act(
            f,
            f"field-follow-ups/{task['id']}/events",
            {"action": "CLAIM", "reason": "I will record a pilot follow-up."},
        ).status_code
        == 200
    )
    assert (
        act(f, "review-events", {"state": "CLOSED_NO_ACTION", "reason": "End review."}).status_code
        == 409
    )
    assert (
        act(
            f,
            f"field-follow-ups/{task['id']}/events",
            {
                "action": "COMPLETE",
                "reason": (
                    "Synthetic visit finding: no current activity observed; no remediation claim."
                ),
            },
        ).status_code
        == 200
    )
    assert act(f, "review-events", {"state": "CLOSED_NO_ACTION"}).status_code == 422
    assert (
        act(
            f,
            "review-events",
            {
                "state": "CLOSED_NO_ACTION",
                "reason": "Review ended after recorded follow-up. No remediation established.",
            },
        ).status_code
        == 200
    )
    resident = (
        f["client"]
        .get(f"/api/v2/resident/reports/{f['a'].report_id}", headers=f["headers"][RESIDENT.subject])
        .json()
    )
    assert resident["reporter_status"] == "UPDATE_AVAILABLE"  # Internal closure does not publish.
    assert (
        act(
            f,
            "reporter-updates",
            {
                "status": "CLOSED",
                "message": "Pilot review ended after your reply and a recorded follow-up.",
            },
        ).status_code
        == 200
    )
    safe = f["client"].get(
        f"/api/v2/resident/reports/{f['a'].report_id}", headers=f["headers"][RESIDENT.subject]
    )
    assert safe.json()["reporter_status"] == "CLOSED"
    assert all(
        x not in safe.text
        for x in (
            "PRIVATE PHASE4 NOTE",
            "Review ended after recorded",
            "assigned_member",
            "actor_user",
        )
    )
    assert act(f, "review-events", {"state": "REOPEN"}).status_code == 422
    assert (
        act(
            f,
            "review-events",
            {"state": "REOPEN", "reason": "A new concern merits another review."},
        ).status_code
        == 200
    )
    assert (
        act(f, "external-references", {"reference": "SYNTHETIC-MANUAL-REFERENCE-42"}).status_code
        == 200
    )
    workspace = detail(f).json()
    assert workspace["review_state"] == "UNDER_REVIEW"
    assert all(
        a["state"] in {"PENDING", "NOT_APPLICABLE"} for a in workspace["processing_attempts"]
    )
    packet = f["client"].get(base(f) + "/export-v2", headers=f["headers"][REVIEWER.subject])
    assert packet.status_code == 200 and packet.json()["schema_version"] == "pilot_case_packet_v2"
    payload = packet.json()["packet"]
    assert (
        packet.json()["sha256"]
        == hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
    )
    assert all(
        s not in packet.text
        for s in (
            "PRIVATE PHASE4 NOTE",
            "latitude",
            "reporter_user_id",
            "object_key",
            "SYNTHETIC-MANUAL-REFERENCE",
        )
    )
    assert (
        f["client"]
        .get(base(f) + "/export", headers=f["headers"][REVIEWER.subject])
        .json()["schema_version"]
        == "pilot_case_packet_v1"
    )


def test_assignment_followup_and_new_routes_cannot_cross_unit_or_escalate(access_fixture):
    f = access_fixture
    with f["sessions"]() as session:
        mine = session.scalar(
            select(Membership.id).where(
                Membership.unit_id == f["unit"], Membership.user_id == f["users"][REVIEWER.subject]
            )
        )
        admin = session.scalar(
            select(Membership.id).where(
                Membership.unit_id == f["unit"], Membership.user_id == f["users"]["admin-a"]
            )
        )
        foreign = session.scalar(
            select(Membership.id).where(Membership.unit_id == f["unit_b"]).limit(1)
        )
    assert act(f, "assignments", {"membership_id": str(admin)}).status_code == 403
    assert (
        act(f, "assignments", {"membership_id": str(foreign)}, actor="admin-a").status_code == 404
    )
    assert act(f, "assignments", {"membership_id": str(mine)}, actor="admin-a").status_code == 200
    queue = (
        f["client"]
        .get(
            f"/api/v2/authority/units/{f['unit']}/cases?assignment=mine",
            headers=f["headers"][REVIEWER.subject],
        )
        .json()
    )
    assert queue["total"] == 1
    assert (
        act(f, "field-follow-ups", {"reason": "Synthetic verification request"}).status_code == 200
    )
    task = detail(f).json()["field_follow_ups"][0]
    assert (
        act(
            f,
            f"field-follow-ups/{task['id']}/events",
            {"action": "ASSIGN", "membership_id": str(admin), "reason": "No admin privilege"},
        ).status_code
        == 403
    )
    assert (
        act(
            f,
            f"field-follow-ups/{task['id']}/events",
            {"action": "ASSIGN", "membership_id": str(mine), "reason": "Unit-scoped assignment"},
            actor="admin-a",
        ).status_code
        == 200
    )
    for path, body in [
        ("assignments", {"claim_self": True}),
        ("internal-notes", {"body": "x"}),
        ("information-requests", {"prompt": "x"}),
        ("reporter-updates", {"status": "UPDATE_AVAILABLE", "message": "x"}),
        ("field-follow-ups", {"reason": "x"}),
        ("external-references", {"reference": "x"}),
        ("enrichments", {"reason": "x"}),
    ]:
        assert act(f, path, body, revision=0, case=f["b"].case_id).status_code == 404
        assert act(f, path, body, actor=RESIDENT.subject, revision=0).status_code == 404
    assert (
        f["client"]
        .post(
            base(f, case=f["b"].case_id) + "/live-context",
            headers=f["headers"][REVIEWER.subject],
            json={},
        )
        .status_code
        == 404
    )
    assert (
        f["client"]
        .get(base(f) + "/live-context", headers=f["headers"][REVIEWER.subject])
        .status_code
        == 405
    )
    for path in ("history", "export-v2", f"evidence/{uuid4()}"):
        assert (
            f["client"]
            .get(base(f, case=f["b"].case_id) + "/" + path, headers=f["headers"][REVIEWER.subject])
            .status_code
            == 404
        )
    assert (
        f["client"]
        .get(
            f"/api/v2/authority/units/{f['unit_b']}/reviewers",
            headers=f["headers"][REVIEWER.subject],
        )
        .status_code
        == 404
    )


def test_second_reviewer_revision_conflict_does_not_overwrite(access_fixture):
    f = access_fixture
    revision = detail(f).json()["revision"]
    barrier = Barrier(2)

    def write(actor):
        barrier.wait()
        return act(
            f,
            "internal-notes",
            {"body": "Synthetic concurrent note " + actor},
            actor=actor,
            revision=revision,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(write, [REVIEWER.subject, "admin-a"]))
    assert sorted(r.status_code for r in results) == [200, 409]
    current = detail(f).json()
    assert current["revision"] == revision + 1
    assert (
        len([n for n in current["internal_notes"] if n.startswith("Synthetic concurrent note")])
        == 1
    )

    before_review = detail(f).json()["revision"]
    assert (
        act(
            f,
            "review-events",
            {"state": "UNDER_REVIEW", "reason": "Current assessment"},
            revision=before_review,
        ).status_code
        == 200
    )
    assert (
        act(
            f,
            "review-events",
            {"state": "UNDER_REVIEW", "reason": "Stale assessment"},
            actor="admin-a",
            revision=before_review,
        ).status_code
        == 409
    )


def test_provider_failure_freezes_version_without_google_or_review_mutation(access_fixture, output):
    f = access_fixture
    cancel_initial(f)
    analyzer = FakeAnalyzer(output, failure=AnalysisStatus.TIMEOUT)
    analyzer.settings = CitizenSettings(project="synthetic", timeout_seconds=1)
    f["client"].app.state.citizen_analyzer = analyzer

    class ForbiddenGoogle:
        configured = True
        name = "synthetic_google_should_not_be_called"

        async def fetch(self, *_args):
            raise AssertionError("Saved enrichment must not request Google current observations")

    environment = f["client"].app.state.environment
    environment.providers["air_quality"] = ForbiddenGoogle()
    environment.providers["weather"] = ForbiddenGoogle()
    response = finish_refresh(f, act(f, "enrichments", {"reason": "Synthetic failure rehearsal"}))
    assert response["state"] == "FAILED"
    workspace = detail(f).json()
    assert workspace["review_state"] == "NEW" and workspace["description"]
    assert any(a["safe_reason"] == "TIMEOUT" for a in workspace["processing_attempts"])
    evidence = f["repo"].evidence(
        f["principals"][REVIEWER.subject], f["a"].case_id, UUID(response["version_id"])
    )
    assert all(p["payload"] is None for p in evidence["fragments"])
    assert all(
        p["state"] == "NOT_RETAINED_BY_POLICY"
        for p in evidence["fragments"]
        if p["source"].startswith("GOOGLE")
    )
    assert (
        act(
            f, "internal-notes", {"body": "Manual review remains available after failure."}
        ).status_code
        == 200
    )
    second = finish_refresh(f, act(f, "enrichments", {"reason": "Deliberate new version"}))
    assert second["version_id"] != response["version_id"]
    assert (
        f["repo"].evidence(
            f["principals"][REVIEWER.subject], f["a"].case_id, UUID(response["version_id"])
        )
        == evidence
    )
    assert act(f, "enrichments", {"reason": "Limit rehearsal"}).status_code == 429


def test_policy_disabled_text_only_assessment_and_retention_health_gate(access_fixture, output):
    f = access_fixture
    cancel_initial(f)
    from test_resident import intake

    response, _, _ = intake(f)
    report_id = UUID(response.json()["report_id"])
    with f["sessions"]() as session:
        case_id = session.scalar(select(Case.id).where(Case.report_id == report_id))
    f["repo"].provider_retention_reviewed = False
    enriched = finish_refresh(
        f, act(f, "enrichments", {"reason": "Text-only assessment"}, case=case_id)
    )
    projection = f["repo"].evidence(
        f["principals"][REVIEWER.subject], case_id, UUID(enriched["version_id"])
    )
    rule = next(x for x in projection["fragments"] if x["source"] == "RULES")
    assert (
        rule["payload"]["support_level"] == "INSUFFICIENT" and rule["payload"]["event_type"] is None
    )
    assert rule["payload"]["reason_code"] == "NO_VISUAL_HYPOTHESIS"
    assert (
        next(x for x in projection["fragments"] if x["source"] == "GEMINI")["state"]
        == "NOT_APPLICABLE"
    )
    f["repo"].provider_retention_reviewed = True
    f["repo"].require_maintenance = True
    analyzer = FakeAnalyzer(output, failure=AnalysisStatus.TIMEOUT)
    analyzer.settings = CitizenSettings(project="synthetic", timeout_seconds=1)
    f["client"].app.state.citizen_analyzer = analyzer
    blocked = finish_refresh(f, act(f, "enrichments", {"reason": "Missing retention scheduler"}))
    assert (
        blocked["state"] == "FAILED" and blocked["safe_reason"] == "POLICY_OR_MAINTENANCE_REQUIRED"
    )
    RetentionService(f["repo"], f["store"]).sweep()
    verified = finish_refresh(f, act(f, "enrichments", {"reason": "Verified maintenance"}))
    assert verified["safe_reason"] == "RETRY_EXHAUSTED"
    with f["sessions"].begin() as session:
        from app.persistence.models import MaintenanceHeartbeat

        session.get(MaintenanceHeartbeat, "retention").succeeded_at = f["repo"].clock() - timedelta(
            seconds=121
        )
    f["repo"].limits = f["repo"].limits.model_copy(update={"refreshes_per_hour": 10})
    stale = finish_refresh(f, act(f, "enrichments", {"reason": "Stale maintenance"}))
    assert stale["state"] == "FAILED" and stale["safe_reason"] == "POLICY_OR_MAINTENANCE_REQUIRED"


def test_review_reason_immutability_and_privacy_purge(access_fixture):
    f = access_fixture
    assert (
        act(
            f, "review-events", {"state": "UNDER_REVIEW", "reason": "PRIVATE REVIEW REASON"}
        ).status_code
        == 200
    )
    assert act(f, "external-references", {"reference": "PRIVATE MANUAL REF"}).status_code == 200
    with f["sessions"]() as session:
        event_id = session.scalar(
            select(ReviewEvent.id).where(ReviewEvent.reason == "PRIVATE REVIEW REASON")
        )
    with pytest.raises(IntegrityError), f["sessions"].begin() as session:
        session.execute(
            update(ReviewEvent).where(ReviewEvent.id == event_id).values(reason="Overwrite history")
        )
    f["repo"].delete_report(f["principals"][RESIDENT.subject], f["a"].report_id)
    RetentionService(f["repo"], f["store"]).sweep()
    with f["sessions"]() as session:
        assert session.get(Case, f["a"].case_id).external_reference is None
        assert session.get(ReviewEvent, event_id).reason is None
        assert session.get(Report, f["a"].report_id).description is None


def test_successful_advisory_snapshot_is_frozen_and_expires_with_image(access_fixture, output):
    from datetime import UTC, datetime

    from app.persistence.models import Media

    f = access_fixture
    cancel_initial(f)
    f["repo"].clock = lambda: datetime.now(UTC)
    analyzer = FakeAnalyzer(output)
    analyzer.settings = CitizenSettings(project="synthetic", timeout_seconds=1)
    f["client"].app.state.citizen_analyzer = analyzer
    expiry = datetime.now(UTC) + timedelta(seconds=60)
    with f["sessions"].begin() as session:
        session.get(Media, f["media_a"]).expires_at = expiry
    response = finish_refresh(f, act(f, "enrichments", {"reason": "Synthetic advisory snapshot"}))
    version_id = UUID(response["version_id"])
    read = f["repo"].evidence(f["principals"][REVIEWER.subject], f["a"].case_id, version_id)
    visual = next(x for x in read["fragments"] if x["source"] == "GEMINI")
    rules = next(x for x in read["fragments"] if x["source"] == "RULES")
    assert visual["payload"]["model_version"] == "fake-version-001"
    assert rules["payload"]["support_level"] == "INSUFFICIENT"
    assert rules["payload"]["event_type"] == "uncertain"
    assert rules["expires_at"] == visual["expires_at"] == expiry.isoformat()
    assert detail(f).json()["review_state"] == "NEW"  # No automatic human decision.
    with pytest.raises(IntegrityError), f["sessions"].begin() as session:
        session.execute(
            update(EvidenceFragment)
            .where(EvidenceFragment.version_id == version_id)
            .values(payload={"replacement": "forbidden"})
        )
    f["repo"].clock = lambda: expiry + timedelta(seconds=1)
    expired = f["repo"].evidence(f["principals"][REVIEWER.subject], f["a"].case_id, version_id)
    assert all(
        x["payload"] is None for x in expired["fragments"] if x["source"] in {"GEMINI", "RULES"}
    )
    RetentionService(f["repo"], f["store"]).sweep()
    with f["sessions"]() as session:
        assert session.get(EvidenceVersion, version_id).input_fingerprint is None
        assert all(
            x.payload is None and x.content_sha256 is None
            for x in session.scalars(
                select(EvidenceFragment).where(EvidenceFragment.version_id == version_id)
            )
        )
        assert session.get(Report, f["a"].report_id).description is not None


def test_inflight_revocation_discards_provider_result(access_fixture, output):
    from datetime import UTC, datetime

    f = access_fixture
    cancel_initial(f)
    f["repo"].clock = lambda: datetime.now(UTC)

    class RevokingAnalyzer(FakeAnalyzer):
        async def analyze(self, *args):
            result = await super().analyze(*args)
            with f["sessions"].begin() as session:
                session.execute(
                    update(Membership)
                    .where(
                        Membership.unit_id == f["unit"],
                        Membership.user_id == f["users"][REVIEWER.subject],
                    )
                    .values(state="REVOKED")
                )
            return result

    analyzer = RevokingAnalyzer(output)
    analyzer.settings = CitizenSettings(project="synthetic", timeout_seconds=1)
    f["client"].app.state.citizen_analyzer = analyzer
    response = finish_refresh(
        f, act(f, "enrichments", {"reason": "Synthetic in-flight revocation"})
    )
    assert response["state"] == "CANCELLED"
    with f["sessions"]() as session:
        assert (
            session.scalar(
                select(EvidenceVersion.id).where(EvidenceVersion.case_id == f["a"].case_id)
            )
            is None
        )
    own = f["client"].get(
        f"/api/v2/resident/reports/{f['a'].report_id}", headers=f["headers"][RESIDENT.subject]
    )
    assert own.status_code == 200 and own.json()["description"]


def test_live_context_is_separate_scoped_and_stopped_on_withdrawal(access_fixture):
    from sqlalchemy import func

    f = access_fixture
    headers = f["headers"][REVIEWER.subject]
    with f["sessions"]() as session:
        before = session.scalar(select(func.count()).select_from(EvidenceFragment))
    response = f["client"].post(base(f) + "/live-context", headers=headers, json={})
    assert response.status_code == 200, response.text
    assert response.json()["forecast"]["provider_status"]["status"] == "not_configured"
    assert response.headers["cache-control"] == "private, no-store"
    with f["sessions"].begin() as session:
        assert session.scalar(select(func.count()).select_from(EvidenceFragment)) == before
        session.get(Report, f["a"].report_id).withdrawn_at = f["repo"].clock()
    assert f["client"].post(base(f) + "/live-context", headers=headers, json={}).status_code == 409
    assert act(f, "enrichments", {"reason": "Cannot process withdrawn content"}).status_code == 410


def test_rollback_refuses_unrepresentable_manual_records_without_data_loss(access_fixture):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    from app.persistence.models import Job

    f = access_fixture
    with f["sessions"].begin() as session:
        row = session.scalar(select(Job).where(Job.report_id == f["a"].report_id))
        row.state = "PARTIAL"
    with pytest.raises(IntegrityError):
        command.downgrade(
            Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "seva_0004"
        )
    with f["sessions"]() as session:
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == "seva_0006"
        assert (
            session.scalar(select(Job.state).where(Job.report_id == f["a"].report_id)) == "PARTIAL"
        )
        assert session.get(Report, f["a"].report_id).description is not None


def test_bounded_export_keeps_latest_decision_and_discloses_omissions(access_fixture):
    f = access_fixture
    with f["sessions"].begin() as session:
        case = session.get(Case, f["a"].case_id)
        versions = [
            EvidenceVersion(
                case_id=case.id,
                request_id=uuid4(),
                version=n,
                created_at=f["repo"].clock(),
                expires_at=f["repo"].clock() + timedelta(days=1),
            )
            for n in range(1, 102)
        ]
        session.add_all(versions)
        session.flush()
        for revision in range(2, 503):
            session.add(
                ReviewEvent(
                    case_id=case.id,
                    actor_user_id=f["users"][REVIEWER.subject],
                    unit_id=f["unit"],
                    revision=revision,
                    action="SYNTHETIC_REVIEW",
                    evidence_version_id=versions[-1].id,
                    created_at=f["repo"].clock(),
                )
            )
        case.evidence_sequence, case.latest_evidence_version_id, case.revision = (
            101,
            versions[-1].id,
            502,
        )
    response = f["client"].get(base(f) + "/export-v2", headers=f["headers"][REVIEWER.subject])
    assert response.status_code == 200
    packet = response.json()["packet"]
    assert packet["limits"]["truncated"] and packet["limits"]["total_versions"] == 101
    assert (
        len(packet["evidence_versions"]) == 100
        and packet["evidence_versions"][-1]["version"] == 101
    )
    assert len(packet["review_events"]) == 500 and packet["review_events"][-1]["revision"] == 502
    assert (
        packet["review_events"][-1]["evidence_version_id"] == packet["evidence_versions"][-1]["id"]
    )
