"""Real SQL permissions + signed test access tokens. No test login HTTP route exists."""

import hashlib
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import DBAPIError
from test_persistence import (  # Reuse the guarded disposable-PostgreSQL migration fixture.
    ISSUER,
    OTHER,
    RESIDENT,
    REVIEWER,
    image_bytes,
    submission,
)
from test_persistence import fixture as fixture
from test_persistence import pg as pg

from app.access.limits import AdmissionLimits
from app.access.provision import OperatorConsole
from app.access.service import AccessService
from app.access.tokens import AccessTokenVerifier, InvalidIdentity, TokenSettings
from app.main import create_app
from app.persistence.contracts import AccessDenied, Principal, RateLimited
from app.persistence.database import database
from app.persistence.models import (
    AccessAudit,
    AnalysisAdmission,
    AuthSession,
    AuthSessionSecret,
    Case,
    Identity,
    Membership,
    OperatorGrant,
    Report,
    Unit,
)
from app.persistence.repository import DurableRepository

SETTINGS = TokenSettings(ISSUER, "urn:airshedos:pilot-api", "synthetic-bff")


@pytest.fixture
def persistence_fixture(request):
    return request.getfixturevalue("fixture")


@pytest.fixture(scope="module")
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def signed(key, subject=RESIDENT.subject, *, changes=None, header=None):
    now = int(datetime.now(UTC).timestamp())
    claims = {
        "iss": ISSUER,
        "sub": subject,
        "aud": SETTINGS.audience,
        "client_id": SETTINGS.client_id,
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + 600,
        "scope": "access:airshedos",
    }
    claims.update(changes or {})
    return jwt.encode(
        claims,
        key,
        algorithm="RS256",
        headers={"typ": "at+jwt", "kid": "synthetic-key", **(header or {})},
    )


@pytest.fixture
def access_fixture(persistence_fixture, signing_key):
    f = persistence_fixture
    repo, sessions = f["repo"], f["sessions"]
    with sessions.begin() as session:
        other_unit = session.scalar(select(Unit.id).where(Unit.id != f["unit"]))
        for subject in ("admin-a", "admin-b", "operator", "candidate"):
            user = Identity(issuer=ISSUER, subject=subject, created_at=f["clock"][0])
            session.add(user)
            session.flush()
            f["users"][subject] = user.id
        for subject, unit in (("admin-a", f["unit"]), ("admin-b", other_unit)):
            session.add(
                Membership(
                    user_id=f["users"][subject],
                    unit_id=unit,
                    role="UNIT_ADMIN",
                    state="ACTIVE",
                    approved_by=f["users"]["operator"],
                    approved_at=f["clock"][0],
                )
            )
        session.add(
            OperatorGrant(user_id=f["users"]["operator"], active=True, granted_at=f["clock"][0])
        )
    media_a = f["media"].stage(RESIDENT, image_bytes(), "image/jpeg")
    a = repo.create_report(
        RESIDENT, submission(media_id=media_a), key=uuid4(), key_created_at=f["clock"][0]
    )
    repo.add_internal_note(REVIEWER, a.case_id, expected_revision=0, body="Private reviewer note")
    repo.triage_unit_id = other_unit
    media_b = f["media"].stage(OTHER, image_bytes(), "image/jpeg")
    data_b = submission(media_id=media_b).model_copy(
        update={"description": "Hidden unit B keyword"}
    )
    b = repo.create_report(OTHER, data_b, key=uuid4(), key_created_at=f["clock"][0])
    repo.triage_unit_id = f["unit"]
    headers, principals, session_ids = {}, {}, {}
    with sessions.begin() as session:
        for subject, user_id in f["users"].items():
            binding = uuid4().hex + uuid4().hex
            row = AuthSession(
                user_id=user_id,
                sdk_key_hash=uuid4().hex + uuid4().hex,
                binding_hash=hashlib.sha256(binding.encode()).hexdigest(),
                issuer=ISSUER,
                subject=subject,
                created_at=f["clock"][0],
                idle_expires_at=f["clock"][0] + timedelta(minutes=30),
                absolute_expires_at=f["clock"][0] + timedelta(hours=8),
            )
            session.add(row)
            session.flush()
            principals[subject] = Principal(ISSUER, subject, session_id=row.id)
            session_ids[subject] = row.id
            headers[subject] = {
                "Authorization": "Bearer " + signed(signing_key, subject),
                "X-AirshedOS-Session": binding,
            }
    verifier = AccessTokenVerifier(SETTINGS, keys=lambda kid: signing_key.public_key())
    service = AccessService(repo, verifier, f["media"])
    f |= {
        "service": service,
        "headers": headers,
        "principals": principals,
        "session_ids": session_ids,
        "a": a,
        "b": b,
        "media_a": media_a,
        "media_b": media_b,
        "unit_b": other_unit,
    }
    with TestClient(create_app(access=service, mode="pilot")) as client:
        f["client"] = client
        yield f


def authority(f, suffix="", unit=None, case=None):
    return f"/api/v2/authority/units/{unit or f['unit']}/cases/{case or f['a'].case_id}{suffix}"


def test_resident_own_other_lists_no_private_projection(access_fixture):
    f = access_fixture
    for subject, own, other in (
        (RESIDENT.subject, f["a"], f["b"]),
        (OTHER.subject, f["b"], f["a"]),
    ):
        headers = f["headers"][subject]
        response = f["client"].get("/api/v2/resident/reports?limit=1&offset=0", headers=headers)
        assert response.status_code == 200 and response.json()["total"] == 1
        assert response.json()["items"][0]["id"] == str(own.report_id)
        detail = f["client"].get(f"/api/v2/resident/reports/{own.report_id}", headers=headers)
        assert detail.status_code == 200 and detail.headers["cache-control"] == "private, no-store"
        encoded = detail.text
        assert "Private reviewer note" not in encoded and "reporter_user_id" not in encoded
        assert ISSUER not in encoded and "object_key" not in encoded
        missing = f["client"].get(f"/api/v2/resident/reports/{other.report_id}", headers=headers)
        unknown = f["client"].get(f"/api/v2/resident/reports/{uuid4()}", headers=headers)
        assert missing.status_code == unknown.status_code == 404
        assert missing.json() == unknown.json() == {"detail": "Not found"}


def test_anonymous_cannot_enumerate_detail_list_media_or_export(access_fixture):
    f = access_fixture
    for path in (
        "/api/v2/me",
        "/api/v2/resident/reports",
        f"/api/v2/resident/reports/{f['a'].report_id}",
        f"/api/v2/resident/media/{f['media_a']}",
        authority(f),
        authority(f, "/export"),
        f"/api/v2/authority/units/{f['unit']}/cases",
    ):
        response = f["client"].get(path)
        assert response.status_code == 401
        assert response.headers["cache-control"] == "private, no-store"


def test_citizen_and_role_headers_cannot_call_reviewer_or_admin(access_fixture, signing_key):
    f = access_fixture
    headers = f["headers"][RESIDENT.subject] | {
        "X-Role": "UNIT_ADMIN",
        "X-User-Id": str(f["users"]["admin-a"]),
        "X-Unit-Id": str(f["unit"]),
        "Authorization": "Bearer "
        + signed(signing_key, changes={"roles": ["UNIT_ADMIN"], "unit_id": str(f["unit"])}),
    }
    assert f["client"].get("/api/v2/me", headers=headers).json()["units"] == []
    response = f["client"].post(
        authority(f, "/review-events"),
        headers=headers,
        json={"state": "UNDER_REVIEW", "expected_revision": 1},
    )
    assert response.status_code == 404
    assert (
        f["client"]
        .post(
            f"/api/v2/authority/units/{f['unit']}/membership-proposals",
            headers=headers,
            json={"target_subject": "candidate"},
        )
        .status_code
        == 404
    )
    with pytest.raises(AccessDenied):
        f["service"].approve(f["principals"][RESIDENT.subject], uuid4())


def test_cross_unit_counts_filters_map_detail_actions_media_export(access_fixture):
    f = access_fixture
    reviewer = f["headers"][REVIEWER.subject]
    base = f"/api/v2/authority/units/{f['unit']}"
    queue = f["client"].get(base + "/cases?limit=1&offset=0", headers=reviewer).json()
    assert queue["total"] == 1 and queue["state_counts"] == {"NEW": 1}
    assert queue["items"][0]["id"] == str(f["a"].case_id)
    search = f["client"].get(base + "/cases?q=Hidden", headers=reviewer).json()
    assert search == {"total": 0, "items": [], "state_counts": {}}
    assert f["client"].get(base + "/map", headers=reviewer).json() == [
        {
            "case_id": str(f["a"].case_id),
            "latitude": 28.5,
            "longitude": 77.1,
            "content_expires_at": (f["clock"][0] + timedelta(days=90)).isoformat(),
        }
    ]
    for path in (
        f"/api/v2/authority/units/{f['unit_b']}/cases",
        f"/api/v2/authority/units/{f['unit_b']}/map",
        authority(f, case=f["b"].case_id),
        authority(f, "/export", case=f["b"].case_id),
        authority(f, f"/media/{f['media_b']}", case=f["b"].case_id),
        authority(f, unit=f["unit_b"], case=f["b"].case_id),
    ):
        assert f["client"].get(path, headers=reviewer).status_code == 404
    assert (
        f["client"]
        .post(
            authority(f, "/review-events", case=f["b"].case_id),
            headers=reviewer,
            json={"state": "UNDER_REVIEW", "expected_revision": 0},
        )
        .status_code
        == 404
    )
    own = f["client"].get(authority(f, f"/media/{f['media_a']}"), headers=reviewer)
    assert own.status_code == 200 and own.headers["content-type"] == "image/jpeg"
    assert (
        f["client"]
        .get(f"/api/v2/resident/media/{f['media_a']}", headers=f["headers"][OTHER.subject])
        .status_code
        == 404
    )
    packet = f["client"].get(authority(f, "/export"), headers=reviewer)
    assert packet.status_code == 200 and packet.json()["delivery_mode"] == "MANUAL_EXPORT"
    assert all(
        s not in packet.text
        for s in ("Private reviewer note", ISSUER, "description", "latitude", "object_key")
    )


def test_unit_admin_proposal_is_not_grant_and_cannot_cross_scope_or_escalate(access_fixture):
    f = access_fixture
    headers = f["headers"]["admin-a"]
    route = f"/api/v2/authority/units/{f['unit']}/membership-proposals"
    assert (
        f["client"]
        .get(f"/api/v2/authority/units/{f['unit']}/memberships", headers=headers)
        .status_code
        == 200
    )
    assert (
        f["client"]
        .get(f"/api/v2/authority/units/{f['unit_b']}/memberships", headers=headers)
        .status_code
        == 404
    )
    assert (
        f["client"]
        .post(route, headers=headers, json={"target_subject": "candidate", "role": "UNIT_ADMIN"})
        .status_code
        == 422
    )
    assert (
        f["client"]
        .post(
            route,
            headers=headers,
            json={"target_subject": "candidate", "unit_id": str(f["unit_b"])},
        )
        .status_code
        == 422
    )
    created = f["client"].post(route, headers=headers, json={"target_subject": "candidate"})
    assert created.status_code == 201 and created.json()["state"] == "PENDING"
    assert f["client"].get("/api/v2/me", headers=f["headers"]["candidate"]).json()["units"] == []
    with pytest.raises(AccessDenied):
        f["service"].approve(f["principals"]["admin-a"], created.json()["id"])
    f["service"].approve(f["principals"]["operator"], created.json()["id"])
    assert (
        f["client"].get("/api/v2/me", headers=f["headers"]["candidate"]).json()["units"][0]["role"]
        == "REVIEWER"
    )
    assert (
        f["client"]
        .post(route, headers=headers, json={"target_subject": "unverified-email@example.invalid"})
        .status_code
        == 404
    )


def test_membership_revocation_immediate_for_reads_actions_export_media(access_fixture):
    f = access_fixture
    with f["sessions"]() as session:
        member = session.scalar(
            select(Membership.id).where(Membership.user_id == f["users"][REVIEWER.subject])
        )
        admin = session.scalar(
            select(Membership.id).where(Membership.user_id == f["users"]["admin-a"])
        )
    route = f"/api/v2/authority/units/{f['unit']}/memberships"
    assert (
        f["client"].post(f"{route}/{admin}/suspend", headers=f["headers"]["admin-a"]).status_code
        == 404
    )
    assert (
        f["client"].post(f"{route}/{member}/suspend", headers=f["headers"]["admin-a"]).status_code
        == 200
    )
    headers = f["headers"][REVIEWER.subject]  # Same still-valid signed access token/session.
    for path in (authority(f), authority(f, "/export"), authority(f, f"/media/{f['media_a']}")):
        assert f["client"].get(path, headers=headers).status_code == 404
    assert (
        f["client"]
        .post(
            authority(f, "/review-events"),
            headers=headers,
            json={"state": "UNDER_REVIEW", "expected_revision": 1},
        )
        .status_code
        == 404
    )


@pytest.mark.parametrize(
    "kind", ["revoked", "idle", "absolute", "wrong-binding", "wrong-subject", "disabled"]
)
def test_session_invalidity_fails_safely(access_fixture, kind):
    f = access_fixture
    headers = f["headers"][RESIDENT.subject].copy()
    with f["sessions"].begin() as session:
        row = session.get(AuthSession, f["session_ids"][RESIDENT.subject])
        if kind == "revoked":
            row.revoked_at = f["clock"][0]
        if kind == "idle":
            row.idle_expires_at = f["clock"][0] - timedelta(seconds=1)
        if kind == "absolute":
            row.absolute_expires_at = f["clock"][0] - timedelta(seconds=1)
        if kind == "wrong-binding":
            headers["X-AirshedOS-Session"] = "0" * 64
        if kind == "wrong-subject":
            headers["Authorization"] = f["headers"][OTHER.subject]["Authorization"]
        if kind == "disabled":
            session.get(Identity, f["users"][RESIDENT.subject]).active = False
    response = f["client"].get("/api/v2/resident/reports", headers=headers)
    assert response.status_code == 401 and response.json() == {"detail": "Sign in required"}
    if kind != "wrong-binding" and kind != "wrong-subject":
        with pytest.raises(AccessDenied):
            f["repo"].resident_detail(f["principals"][RESIDENT.subject], f["a"].report_id)


@pytest.mark.parametrize(
    "change,header",
    [
        ({"iss": "https://foreign.invalid/"}, {}),
        ({"aud": "wrong-api"}, {}),
        ({"client_id": "wrong-bff"}, {}),
        ({"scope": "openid profile"}, {}),
        ({"iat": 1, "exp": 2}, {}),
        ({"exp": int(datetime.now(UTC).timestamp()) + 3600}, {}),
        ({"jti": None}, {}),
        ({}, {"typ": "JWT"}),
        ({}, {"jku": "https://evil.invalid/jwks"}),
    ],
)
def test_invalid_signed_access_tokens_rejected(access_fixture, signing_key, change, header):
    f = access_fixture
    headers = f["headers"][RESIDENT.subject] | {
        "Authorization": "Bearer " + signed(signing_key, changes=change, header=header)
    }
    assert f["client"].get("/api/v2/me", headers=headers).status_code == 401


def test_invalid_signature_alg_and_missing_claims(access_fixture, signing_key):
    f = access_fixture
    verifier = f["service"].verifier
    wrong = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    for token in (
        signed(wrong),
        "not-a-token",
        jwt.encode(
            {"sub": "resident-a"}, "synthetic-invalid-hmac-key-32-bytes-long", algorithm="HS256"
        ),
    ):
        with pytest.raises(InvalidIdentity):
            verifier.verify(token)
    claims = jwt.decode(
        signed(signing_key),
        signing_key.public_key(),
        algorithms=["RS256"],
        audience=SETTINGS.audience,
    )
    del claims["jti"]
    token = jwt.encode(
        claims, signing_key, algorithm="RS256", headers={"typ": "at+jwt", "kid": "synthetic-key"}
    )
    with pytest.raises(InvalidIdentity):
        verifier.verify(token)


def test_identity_payload_spoofing_rejected_and_no_notes_published(access_fixture):
    f = access_fixture
    route, headers = authority(f, "/review-events"), f["headers"][REVIEWER.subject]
    assert (
        f["client"]
        .post(route, headers=headers, json={"state": "ACKNOWLEDGED", "expected_revision": 1})
        .status_code
        == 422
    )
    for extra in (
        {"actor_user_id": str(f["users"]["operator"])},
        {"unit_id": str(f["unit_b"])},
        {"role": "UNIT_ADMIN"},
    ):
        response = f["client"].post(
            route, headers=headers, json={"state": "UNDER_REVIEW", "expected_revision": 1, **extra}
        )
        assert response.status_code == 422 and response.json() == {"detail": "Invalid request"}
    assert (
        f["client"]
        .post(route, headers=headers, json={"state": "UNDER_REVIEW", "expected_revision": 1})
        .status_code
        == 200
    )
    assert (
        "Private reviewer note"
        not in f["client"]
        .get(f"/api/v2/resident/reports/{f['a'].report_id}", headers=f["headers"][RESIDENT.subject])
        .text
    )


def test_shared_admission_limits_replay_and_paid_budget(access_fixture):
    f = access_fixture
    f["repo"].limits = AdmissionLimits(reports_per_day=2, provider_calls_per_day=1)
    principal, now, key = f["principals"][RESIDENT.subject], f["clock"][0], uuid4()
    first = f["repo"].create_report(principal, submission(), key=key, key_created_at=now)
    assert f["repo"].create_report(principal, submission(), key=key, key_created_at=now).replayed
    with pytest.raises(RateLimited):
        f["repo"].create_report(principal, submission(), key=uuid4(), key_created_at=now)
    token = f["service"].reserve_analysis(
        f["principals"][REVIEWER.subject], f["unit"], f["a"].case_id
    )
    assert token
    with pytest.raises(RateLimited):
        f["service"].reserve_analysis(f["principals"][REVIEWER.subject], f["unit"], first.case_id)
    with f["sessions"]() as session:
        assert (
            session.get(Report, first.report_id) is not None
        )  # Paid budget never unaccepts intake.
        assert session.scalar(select(func.count()).select_from(AnalysisAdmission)) == 1


def test_multi_process_admission_has_one_shared_winner(access_fixture):
    f = access_fixture
    subject, session_id = RESIDENT.subject, f["session_ids"][RESIDENT.subject]
    code = """
import os
from datetime import UTC, datetime
from uuid import UUID, uuid4
from app.access.limits import AdmissionLimits
from app.persistence.contracts import Principal, ReportSubmission, RateLimited
from app.persistence.database import database
from app.persistence.repository import DurableRepository
engine,sessions=database(os.environ['TEST_DATABASE_URL'])
repo=DurableRepository(sessions,require_session=True,limits=AdmissionLimits(reports_per_day=2))
principal=Principal('https://synthetic-issuer.invalid/',os.environ['SUBJECT'],session_id=UUID(os.environ['SESSION']))
try:
 repo.create_report(principal,ReportSubmission(description='Synthetic multiprocess',
  declared_category='UNSURE',reported_latitude=28.5,reported_longitude=77.1),
  key=uuid4(),key_created_at=datetime.now(UTC))
 print('accepted')
except RateLimited: print('limited')
finally: engine.dispose()
"""
    import os

    env = {
        "PATH": os.environ["PATH"],
        "TEST_DATABASE_URL": f["url"],
        "SUBJECT": subject,
        "SESSION": str(session_id),
    }
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", code],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            stdout=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    results = []
    for p in processes:
        out, _ = p.communicate(timeout=30)
        assert p.returncode == 0
        results.append(out.strip())
    assert sorted(results) == ["accepted", "limited"]


def test_offline_operator_bootstrap_unit_creation_and_role_boundary(persistence_fixture):
    f = persistence_fixture
    console = OperatorConsole(f["sessions"], database_role="seva_test", issuer=ISSUER)
    with pytest.raises(AccessDenied):
        console.bootstrap(OTHER.subject, approved_initial_subject=RESIDENT.subject)
    wrong = OperatorConsole(f["sessions"], database_role="not_the_login_role", issuer=ISSUER)
    with pytest.raises(AccessDenied):
        wrong.bootstrap(RESIDENT.subject, approved_initial_subject=RESIDENT.subject)
    console.bootstrap(RESIDENT.subject, approved_initial_subject=RESIDENT.subject)
    with pytest.raises(AccessDenied):
        console.bootstrap(RESIDENT.subject, approved_initial_subject=RESIDENT.subject)
    unit = console.execute(
        RESIDENT.subject,
        "create-unit",
        target_subject=OTHER.subject,
        name="Synthetic staffed intake",
    )
    with f["sessions"]() as session:
        member = session.scalar(select(Membership).where(Membership.unit_id == unit))
        assert member.role == "UNIT_ADMIN" and member.user_id == f["users"][OTHER.subject]
        assert session.scalar(select(func.count()).select_from(AccessAudit)) == 2
    with pytest.raises(AccessDenied):
        console.execute(
            OTHER.subject, "create-unit", target_subject=OTHER.subject, name="Not approved"
        )


def test_pilot_blocks_every_legacy_domain_route_and_unconfigured_stays_closed():
    with TestClient(create_app(mode="pilot")) as client:
        for path in (
            "/api/v1/incidents",
            "/api/v1/review/cases",
            "/api/v1/handoffs",
            "/api/v1/environment/context",
        ):
            assert client.get(path).status_code == 404
        assert client.get("/ready").status_code == 503
        assert client.get("/api/v2/resident/reports").status_code == 401
        assert client.get("/health").json() == {"status": "ok"}


def test_restricted_api_and_session_roles_enforce_column_and_ciphertext_boundaries(access_fixture):
    f = access_fixture
    roles = ("seva_access_test_role", "seva_session_test_role")
    sql = (Path(__file__).resolve().parents[1] / "scripts/pilot_roles.sql").read_text()
    sql = sql.replace(':"api_role"', roles[0]).replace(':"session_role"', roles[1])
    with f["engine"].begin() as connection:
        for role in roles:
            connection.execute(text(f"CREATE ROLE {role} NOLOGIN NOINHERIT"))
        connection.exec_driver_sql(sql)
    engines = []
    try:
        for role in roles:
            engine, sessions = database(f["url"])
            engines.append(engine)

            def set_role(dbapi, _record, role=role):
                dbapi.execute(f"SET ROLE {role}")
                dbapi.commit()

            event.listen(engine, "connect", set_role)
            if role == roles[0]:
                repo = DurableRepository(sessions)
                service = AccessService(repo, f["service"].verifier)
                with TestClient(create_app(access=service, mode="pilot")) as client:
                    assert (
                        client.get("/api/v2/me", headers=f["headers"][RESIDENT.subject]).status_code
                        == 200
                    )
                    assert (
                        client.post(
                            authority(f, "/review-events"),
                            headers=f["headers"][REVIEWER.subject],
                            json={"state": "UNDER_REVIEW", "expected_revision": 1},
                        ).status_code
                        == 200
                    )
                with pytest.raises(DBAPIError), sessions.begin() as session:
                    session.scalar(select(AuthSessionSecret))
                with pytest.raises(DBAPIError), sessions.begin() as session:
                    session.execute(text("UPDATE unit_memberships SET role='UNIT_ADMIN'"))
            else:
                with sessions.begin() as session:
                    # The BFF can take identity locks but cannot reactivate accounts.
                    assert (
                        session.scalar(
                            select(Identity)
                            .where(Identity.id == f["users"][RESIDENT.subject])
                            .with_for_update(read=True)
                        )
                        is not None
                    )
                    session.scalar(select(AuthSessionSecret))
                with pytest.raises(DBAPIError), sessions.begin() as session:
                    session.execute(text("UPDATE users SET active=true"))
                with pytest.raises(DBAPIError), sessions.begin() as session:
                    session.scalar(select(Case))
    finally:
        for engine in engines:
            engine.dispose()
        with f["engine"].begin() as connection:
            for role in roles:
                connection.execute(text(f"DROP OWNED BY {role}"))
                connection.execute(text(f"DROP ROLE {role}"))
