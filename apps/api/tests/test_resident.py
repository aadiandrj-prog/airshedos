import io
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.exc import IntegrityError
from test_access import access_fixture as access_fixture
from test_access import fixture as fixture
from test_access import persistence_fixture as persistence_fixture
from test_access import pg as pg
from test_access import signing_key as signing_key
from test_persistence import OTHER, RESIDENT, REVIEWER, image_bytes, initial_request

from app.persistence.contracts import FirmsPayload, FragmentInput, NotFound
from app.persistence.models import (
    Case,
    IdempotencyKey,
    InformationRequest,
    Job,
    Report,
    ReportSupplement,
)
from app.persistence.retention import RetentionService
from app.resident.service import ResidentService
from app.resident.storage import PREFIX, S3PrivateMediaStore


def intake(f, *, principal=RESIDENT.subject, key=None, **changes):
    body = {
        "description": "Synthetic resident form report",
        "reported_place": "Synthetic north gate",
        "declared_category": "UNSURE",
        "reported_latitude": 28.5,
        "reported_longitude": 77.1,
        "declared_capture_at": None,
        "media_id": None,
        **changes,
    }
    headers = f["headers"][principal] | {
        "Idempotency-Key": str(key or uuid4()),
        "Idempotency-Key-Created-At": f["clock"][0].isoformat(),
    }
    return f["client"].post("/api/v2/resident/reports", headers=headers, json=body), headers, body


def request_information(f, report_id):
    with f["sessions"]() as session:
        case = session.scalar(select(Case).where(Case.report_id == report_id))
        case_id, revision = case.id, case.revision
    return ResidentService(f["repo"]).request_information(
        f["principals"][REVIEWER.subject],
        case_id,
        expected_revision=revision,
        prompt="Please provide an update about the activity.",
    )


def test_http_intake_durable_receipt_replay_unknown_time_and_no_ai_dependency(access_fixture):
    f = access_fixture

    # If the submission accidentally invokes AI, this fixture fails rather than silently
    # treating a provider outage as a successful analysis.
    class NoAnalysis:
        async def analyze(self, *args, **kwargs):
            raise AssertionError("Resident acceptance must not call AI")

    f["client"].app.state.citizen_analyzer = NoAnalysis()
    response, headers, body = intake(f)
    assert response.status_code == 201
    receipt = response.json()
    assert receipt["status"] == "RECEIVED" and receipt["processing"] == "PENDING"
    assert "case_id" not in receipt and "reporter_user_id" not in receipt
    replay = f["client"].post("/api/v2/resident/reports", headers=headers, json=body)
    assert replay.status_code == 200 and replay.headers["Idempotent-Replayed"] == "true"
    assert replay.json()["report_id"] == receipt["report_id"]
    with f["sessions"]() as session:
        assert (
            session.scalar(
                select(func.count()).select_from(Case).where(Case.report_id == receipt["report_id"])
            )
            == 1
        )
        assert (
            session.scalar(
                select(func.count()).select_from(Job).where(Job.report_id == receipt["report_id"])
            )
            == 1
        )
    detail = (
        f["client"].get(f"/api/v2/resident/reports/{receipt['report_id']}", headers=headers).json()
    )
    assert detail["declared_capture_at"] is None and detail["capture_time_basis"] == "unknown"
    assert detail["processing"]["visual_state"] == "NOT_APPLICABLE"
    lookup = f["client"].get(
        f"/api/v2/resident/submissions/{headers['Idempotency-Key']}", headers=headers
    )
    assert lookup.status_code == 200 and lookup.json()["report_id"] == receipt["report_id"]
    assert (
        f["client"]
        .get(
            f"/api/v2/resident/submissions/{headers['Idempotency-Key']}",
            headers=f["headers"][OTHER.subject],
        )
        .status_code
        == 404
    )
    assert (
        f["client"]
        .post(
            "/api/v2/resident/reports",
            headers=headers,
            json=body | {"user_id": str(f["users"][OTHER.subject])},
        )
        .status_code
        == 422
    )
    assert (
        f["client"]
        .post(
            "/api/v2/resident/reports",
            headers=headers,
            json=body | {"description": "Changed input"},
        )
        .status_code
        == 409
    )


def test_failed_database_commit_has_no_receipt_or_partial_records(access_fixture):
    f = access_fixture
    with f["sessions"]() as session:
        before = session.scalar(select(func.count()).select_from(Report))

    def fail(*_args):
        raise IntegrityError("Synthetic insert failure", {}, Exception("synthetic"))

    event.listen(Job, "before_insert", fail)
    try:
        response, _, _ = intake(f)
        assert response.status_code == 503 and "report_id" not in response.json()
    finally:
        event.remove(Job, "before_insert", fail)
    with f["sessions"]() as session:
        assert session.scalar(select(func.count()).select_from(Report)) == before


def test_private_image_consent_limits_and_expiry(access_fixture):
    f = access_fixture
    headers = f["headers"][RESIDENT.subject]
    # Pillow reports some damaged PNG chunk checksums as SyntaxError, not OSError.
    from PIL import Image

    png = io.BytesIO()
    Image.new("RGB", (8, 8), "gray").save(png, "PNG")
    corrupted = bytearray(png.getvalue())
    corrupted[corrupted.index(b"IDAT") + 4] ^= 1
    rejected = f["client"].post(
        "/api/v2/resident/media",
        headers=headers,
        files={"image": ("synthetic.png", bytes(corrupted), "image/png")},
        data={"retention_consent": "true"},
    )
    assert rejected.status_code == 422 and "Traceback" not in rejected.text
    for consent in (None, "false"):
        response = f["client"].post(
            "/api/v2/resident/media",
            headers=headers,
            files={"image": ("private-original-name.jpg", image_bytes(), "image/jpeg")},
            data={} if consent is None else {"retention_consent": consent},
        )
        assert response.status_code == 422
    response = f["client"].post(
        "/api/v2/resident/media",
        headers=headers,
        files={"image": ("private-original-name.jpg", image_bytes(), "image/jpeg")},
        data={"retention_consent": "true"},
    )
    assert response.status_code == 201 and set(response.json()) == {"id", "state", "expires_at"}
    media_id = response.json()["id"]
    received, _, _ = intake(f, media_id=media_id)
    assert received.status_code == 201
    assert f["client"].get(f"/api/v2/resident/media/{media_id}", headers=headers).status_code == 200
    assert (
        f["client"]
        .get(f"/api/v2/resident/media/{media_id}", headers=f["headers"][OTHER.subject])
        .status_code
        == 404
    )
    # Raw request size is bounded even before multipart parsing/auth dependencies.
    oversized = f["client"].post(
        "/api/v2/resident/media",
        headers=headers | {"Content-Type": "multipart/form-data; boundary=x"},
        content=b"x" * (4_000_000 + 65537),
    )
    assert oversized.status_code == 413


def test_append_only_reply_scoped_idempotent_and_parent_evidence_unchanged(access_fixture):
    f = access_fixture
    report_id = f["a"].report_id
    version = f["repo"].append_evidence(
        f["principals"][REVIEWER.subject],
        f["a"].case_id,
        request_id=initial_request(f, report_id),
        fragments=[
            FragmentInput(
                payload=FirmsPayload(dataset="VIIRS_NOAA20_NRT", detection_count=0),
                retrieved_at=f["clock"][0],
            )
        ],
    )
    before = f["repo"].evidence(f["principals"][REVIEWER.subject], f["a"].case_id, version)
    request_id = request_information(f, report_id)
    media_id = f["media"].stage(f["principals"][RESIDENT.subject], image_bytes(), "image/jpeg")
    path = f"/api/v2/resident/reports/{report_id}/information-requests/{request_id}/replies"
    headers = f["headers"][RESIDENT.subject] | {
        "Idempotency-Key": str(uuid4()),
        "Idempotency-Key-Created-At": f["clock"][0].isoformat(),
    }
    body = {"body": "Synthetic supplementary statement", "media_id": str(media_id)}
    assert (
        f["client"]
        .post(
            path,
            headers=f["headers"][OTHER.subject]
            | {
                "Idempotency-Key": str(uuid4()),
                "Idempotency-Key-Created-At": f["clock"][0].isoformat(),
            },
            json=body,
        )
        .status_code
        == 404
    )
    accepted = f["client"].post(path, headers=headers, json=body)
    assert accepted.status_code == 201
    replay = f["client"].post(path, headers=headers, json=body)
    assert replay.status_code == 200 and replay.json()["id"] == accepted.json()["id"]
    assert f["client"].post(path, headers=headers, json={"body": "Different"}).status_code == 409
    assert f["repo"].evidence(f["principals"][REVIEWER.subject], f["a"].case_id, version) == before
    detail = f["client"].get(f"/api/v2/resident/reports/{report_id}", headers=headers).json()
    assert (
        detail["description"] == "Synthetic smoke report" and detail["declared_capture_at"] is None
    )
    assert detail["information_requests"][0]["state"] == "ANSWERED"
    assert detail["supplements"][0]["body"] == body["body"]
    assert "Private reviewer note" not in str(detail) and "author_id" not in str(detail)
    assert f["media"].read(f["principals"][RESIDENT.subject], media_id)
    with pytest.raises(IntegrityError), f["sessions"].begin() as session:
        session.execute(update(ReportSupplement).values(body="Silently changed"))
    f["repo"].delete_report(f["principals"][RESIDENT.subject], report_id)
    with pytest.raises(NotFound):
        f["media"].read(f["principals"][RESIDENT.subject], media_id)
    RetentionService(f["repo"], f["store"]).sweep()
    with f["sessions"]() as session:
        assert session.scalar(select(ReportSupplement.body)) is None
        assert session.scalar(select(InformationRequest.prompt)) is None
        assert all(
            k.fingerprint is None
            for k in session.scalars(
                select(IdempotencyKey).where(IdempotencyKey.report_id == report_id)
            )
        )


def test_local_context_is_optional_and_never_persisted(access_fixture):
    f = access_fixture
    response = f["client"].post(
        "/api/v2/resident/context",
        json={"report_id": str(f["a"].report_id)},
        headers=f["headers"][RESIDENT.subject],
    )
    assert (
        f["client"]
        .get(
            "/api/v2/resident/context?latitude=28.5&longitude=77.1",
            headers=f["headers"][RESIDENT.subject],
        )
        .status_code
        == 405
    )
    assert response.status_code == 200 and response.json()["air_quality"] is None
    assert response.json()["weather"] is None
    assert response.headers["cache-control"] == "private, no-store"
    result, _, _ = intake(f)
    assert result.status_code == 201  # No source availability required.


def test_private_s3_adapter_contract_and_safe_keys():
    class FakeS3:
        def __init__(self):
            self.objects = {}
            self.put = None

        def put_object(self, **kwargs):
            self.put = kwargs
            self.objects[kwargs["Key"]] = kwargs["Body"]

        def get_object(self, **kwargs):
            data = self.objects[kwargs["Key"]]
            return {"Body": io.BytesIO(data), "ContentLength": len(data)}

        def delete_object(self, **kwargs):
            self.objects.pop(kwargs["Key"], None)

    client = FakeS3()
    store = S3PrivateMediaStore(client, "synthetic-private-bucket")
    key = uuid4().hex
    store.put_derivative(key, b"synthetic cleaned derivative")
    assert client.put["Key"] == PREFIX + key and client.put["CacheControl"] == "private, no-store"
    assert "ACL" not in client.put and "Metadata" not in client.put
    assert store.read(key) == b"synthetic cleaned derivative"
    store.delete(key)
    assert not client.objects
    with pytest.raises(ValueError):
        store.read("../outside")
    assert S3PrivateMediaStore.from_env({}) is None
    with pytest.raises(ValueError):
        S3PrivateMediaStore.from_env(
            {
                "PRIVATE_MEDIA_APPROVED": "1",
                "MEDIA_BACKEND": "s3",
                "S3_ENDPOINT_URL": "https://evil.invalid",
            }
        )
