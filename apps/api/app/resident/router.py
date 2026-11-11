import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from pydantic import AwareDatetime
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.access.limits import charge
from app.access.router import Actor
from app.environment.models import (
    AirQualityObservation,
    EnvironmentalSourceStatus,
    MeteorologicalObservation,
)
from app.persistence.contracts import Gone, MediaRead, NotFound, StrictModel
from app.persistence.media import MAX_UPLOAD_BYTES
from app.persistence.models import Case, Unit
from app.resident.contracts import (
    ResidentReceipt,
    ResidentSubmission,
    SupplementReceipt,
    SupplementSubmission,
)
from app.resident.service import ResidentService

router = APIRouter(prefix="/api/v2/resident", tags=["Resident intake"])
Key = Annotated[UUID, Header(alias="Idempotency-Key")]
Created = Annotated[AwareDatetime, Header(alias="Idempotency-Key-Created-At")]


@router.post("/reports", response_model=ResidentReceipt, status_code=201)
def accept(
    request: Request,
    response: Response,
    principal: Actor,
    body: ResidentSubmission,
    key: Key,
    created_at: Created,
):
    try:
        result = ResidentService(request.app.state.access.repo).accept(
            principal, body, key, created_at
        )
    except ValueError as exc:
        raise HTTPException(422, "Invalid submission details or retry time") from exc
    if result.replayed:
        response.status_code = 200
        response.headers["Idempotent-Replayed"] = "true"
    return result


@router.get("/submissions/{key}", response_model=ResidentReceipt)
def submission(request: Request, principal: Actor, key: UUID):
    return ResidentService(request.app.state.access.repo).submission(principal, key)


@router.post(
    "/reports/{report_id}/information-requests/{request_id}/replies",
    response_model=SupplementReceipt,
    status_code=201,
)
def reply(
    request: Request,
    response: Response,
    principal: Actor,
    report_id: UUID,
    request_id: UUID,
    body: SupplementSubmission,
    key: Key,
    created_at: Created,
):
    try:
        result = ResidentService(request.app.state.access.repo).reply(
            principal, report_id, request_id, body, key, created_at
        )
    except ValueError as exc:
        raise HTTPException(422, "Invalid reply") from exc
    if result.replayed:
        response.status_code = 200
        response.headers["Idempotent-Replayed"] = "true"
    return result


@router.post("/media", response_model=MediaRead, status_code=201)
async def stage(
    request: Request,
    principal: Actor,
    image: Annotated[UploadFile, File()],
    retention_consent: Annotated[Literal["true"], Form()],
):
    try:
        form = await request.form()
        if set(form) != {"image", "retention_consent"} or any(
            len(form.getlist(key)) != 1 for key in form
        ):
            raise HTTPException(422, "Provide one image and explicit retention consent")
        service = request.app.state.access
        if service.media is None:
            raise HTTPException(503, "Private image storage unavailable; submit text only")
        data = await image.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Image exceeds 4,000,000 bytes; submit text only")
        media_id = await run_in_threadpool(
            service.media.stage, principal, data, image.content_type or ""
        )
        with service.repo.sessions.begin() as session:
            user = service.repo.identity(session, principal)
            from app.persistence.models import Media

            media = session.get(Media, media_id)
            if media.owner_id != user.id:
                raise HTTPException(404, "Not found")
            return MediaRead(id=media.id, state=media.state, expires_at=media.expires_at)
    except ValueError as exc:
        raise HTTPException(
            422, "Use one still JPEG/PNG, at most 4,000,000 bytes and 16 MP"
        ) from exc
    finally:
        await image.close()


class LocalContext(StrictModel):
    air_quality: AirQualityObservation | None
    weather: MeteorologicalObservation | None
    sources: dict[str, EnvironmentalSourceStatus]
    retrieved_at: datetime
    expires_at: datetime


class LocalContextRequest(StrictModel):
    report_id: UUID


@router.post("/context", response_model=LocalContext)
async def local_context(
    request: Request,
    principal: Actor,
    body: LocalContextRequest,
):
    access, environment = request.app.state.access, request.app.state.environment

    def authorised_report(session):
        user, report = access.repo._owned_report(session, principal, body.report_id, lock=True)
        if report.withdrawn_at:
            raise Gone("Withdrawn report cannot request context")
        case = session.scalar(select(Case).where(Case.report_id == report.id))
        unit = (
            session.scalar(
                select(Unit).where(Unit.id == case.assigned_unit_id).with_for_update(read=True)
            )
            if case
            else None
        )
        if unit is None or unit.approved_at is None or unit.is_prototype:
            raise NotFound("Authorised case context not available")
        return user, report

    with access.repo.sessions.begin() as session:
        user, report = authorised_report(session)
        latitude, longitude = report.reported_latitude, report.reported_longitude
        charge(
            session,
            scope=user.id,
            rule="LOCAL_CONTEXT",
            period="hour",
            maximum=access.repo.limits.context_per_hour,
        )
        for name in ("air_quality", "weather"):
            if environment.providers[name].configured:
                charge(
                    session,
                    scope="global",
                    rule="PAID_ANALYSIS",
                    period="day",
                    maximum=access.repo.limits.provider_calls_per_day,
                )
    # Request/volatile cache only. No report, evidence, job, hash or backup persistence.
    aq, weather = await asyncio.gather(
        environment.resident_source("air_quality", latitude, longitude),
        environment.resident_source("weather", latitude, longitude),
    )
    with access.repo.sessions.begin() as session:
        _, current_report = authorised_report(session)
        case_deadline = current_report.content_expires_at
    now = datetime.now(UTC)
    deadlines = [now + timedelta(seconds=900), case_deadline]
    for result in (aq, weather):
        if result.data:
            deadlines.append(result.data.retrieved_at + timedelta(seconds=900))
    return LocalContext(
        air_quality=aq.data,
        weather=weather.data,
        sources={"air_quality": aq.source, "weather": weather.source},
        retrieved_at=now,
        expires_at=min(deadlines),
    )


class ResidentUploadLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if not (
            scope["type"] == "http"
            and scope["path"] == "/api/v2/resident/media"
            and scope["method"] == "POST"
        ):
            return await self.app(scope, receive, send)
        from fastapi.responses import JSONResponse

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > MAX_UPLOAD_BYTES + 65536:
                return await JSONResponse(
                    {"detail": "Image request too large; submit text only"},
                    status_code=413,
                    headers={"Cache-Control": "private, no-store"},
                )(scope, receive, send)
            if not message.get("more_body", False):
                break

        async def bounded_receive():
            nonlocal body
            if body is not None:
                data, body = bytes(body), None
                return {"type": "http.request", "body": data, "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
