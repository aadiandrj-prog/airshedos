from dataclasses import replace
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.routing import APIRoute

from app.access.router import Actor
from app.authority.contracts import (
    AssignmentCommand,
    AuthorityPacket,
    EmptyCommand,
    EnrichmentRead,
    FieldCommand,
    InformationCommand,
    NoteCommand,
    PublicationCommand,
    ReasonCommand,
    ReferenceCommand,
    RevisionRead,
)
from app.authority.service import AuthorityService
from app.resident.service import ResidentService


class ReviewRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe(request):
            try:
                return await handler(request)
            except ValueError as exc:
                raise HTTPException(422, "Invalid review action or missing reason") from exc

        return safe


router = APIRouter(
    prefix="/api/v2/authority/units/{unit_id}", tags=["Pilot human review"], route_class=ReviewRoute
)


def service(request: Request):
    return AuthorityService(request.app.state.access)


Service = Annotated[AuthorityService, Depends(service)]


@router.post("/cases/{case_id}/assignments", response_model=RevisionRead)
def assign(principal: Actor, api: Service, unit_id: UUID, case_id: UUID, body: AssignmentCommand):
    return {"revision": api.assign(replace(principal, unit_id=unit_id), case_id, body)}


@router.post("/cases/{case_id}/internal-notes", response_model=RevisionRead)
def note(principal: Actor, api: Service, unit_id: UUID, case_id: UUID, body: NoteCommand):
    api.repo.add_internal_note(
        replace(principal, unit_id=unit_id),
        case_id,
        expected_revision=body.expected_revision,
        body=body.body,
    )
    return {"revision": body.expected_revision + 1}


@router.post("/cases/{case_id}/field-follow-ups", response_model=RevisionRead)
def request_field(
    principal: Actor, api: Service, unit_id: UUID, case_id: UUID, body: ReasonCommand
):
    api.repo.request_verification(
        replace(principal, unit_id=unit_id),
        case_id,
        expected_revision=body.expected_revision,
        instructions=body.reason,
    )
    return {"revision": body.expected_revision + 1}


@router.post("/cases/{case_id}/field-follow-ups/{task_id}/events", response_model=RevisionRead)
def field_event(
    principal: Actor, api: Service, unit_id: UUID, case_id: UUID, task_id: UUID, body: FieldCommand
):
    return {
        "revision": api.field_event(replace(principal, unit_id=unit_id), case_id, task_id, body)
    }


@router.post("/cases/{case_id}/reporter-updates", response_model=RevisionRead)
def publish(principal: Actor, api: Service, unit_id: UUID, case_id: UUID, body: PublicationCommand):
    return {"revision": api.publish(replace(principal, unit_id=unit_id), case_id, body)}


@router.post("/cases/{case_id}/information-requests", response_model=RevisionRead)
def information(
    principal: Actor, api: Service, unit_id: UUID, case_id: UUID, body: InformationCommand
):
    ResidentService(api.repo).request_information(
        replace(principal, unit_id=unit_id),
        case_id,
        expected_revision=body.expected_revision,
        prompt=body.prompt,
    )
    return {"revision": body.expected_revision + 1}


@router.post("/cases/{case_id}/external-references", response_model=RevisionRead)
def reference(principal: Actor, api: Service, unit_id: UUID, case_id: UUID, body: ReferenceCommand):
    return {"revision": api.reference(replace(principal, unit_id=unit_id), case_id, body)}


@router.get("/cases/{case_id}/history")
def history(
    principal: Actor,
    api: Service,
    unit_id: UUID,
    case_id: UUID,
    before_revision: int | None = Query(None, ge=1),
):
    return api.history(replace(principal, unit_id=unit_id), case_id, before_revision)


@router.get("/cases/{case_id}/evidence/{version_id}")
def evidence(principal: Actor, api: Service, unit_id: UUID, case_id: UUID, version_id: UUID):
    return api.repo.evidence(replace(principal, unit_id=unit_id), case_id, version_id)


@router.get("/cases/{case_id}/export-v2", response_model=AuthorityPacket)
def packet(principal: Actor, api: Service, unit_id: UUID, case_id: UUID):
    return api.packet(replace(principal, unit_id=unit_id), case_id)


@router.get("/reviewers")
def reviewers(principal: Actor, api: Service, unit_id: UUID):
    # Minimal roster for assignment. No email/subject/profile lookup for reviewers.
    from sqlalchemy import select

    from app.persistence.models import Identity, Membership

    with api.repo.sessions.begin() as session:
        api.access._unit(session, principal, unit_id)
        return [
            {
                "id": str(m.id),
                "role": m.role,
                "label": f"{m.role.replace('_', ' ').title()} {str(m.id)[:8]}",
            }
            for m in session.scalars(
                select(Membership)
                .join(Identity, Identity.id == Membership.user_id)
                .where(
                    Membership.unit_id == unit_id,
                    Membership.state == "ACTIVE",
                    Membership.approved_at.is_not(None),
                    Membership.approved_by.is_not(None),
                    Identity.active.is_(True),
                )
                .order_by(Membership.id)
                .limit(100)
            )
        ]


@router.get("/membership-proposals")
def proposals(principal: Actor, api: Service, unit_id: UUID):
    from sqlalchemy import select

    from app.persistence.models import MembershipProposal

    with api.repo.sessions.begin() as session:
        api.access._unit(session, principal, unit_id, admin=True)
        return [
            {"id": str(p.id), "state": p.state, "expires_at": p.expires_at.isoformat()}
            for p in session.scalars(
                select(MembershipProposal)
                .where(MembershipProposal.unit_id == unit_id)
                .order_by(MembershipProposal.created_at.desc())
                .limit(50)
            )
        ]


@router.post("/cases/{case_id}/enrichments", response_model=EnrichmentRead, status_code=202)
def enrich(
    principal: Actor,
    api: Service,
    unit_id: UUID,
    case_id: UUID,
    body: ReasonCommand,
):
    from app.processing.queue import enqueue_refresh

    return enqueue_refresh(api.repo, replace(principal, unit_id=unit_id), case_id, body)


@router.post("/cases/{case_id}/live-context")
async def live_context(
    request: Request,
    principal: Actor,
    api: Service,
    unit_id: UUID,
    case_id: UUID,
    body: EmptyCommand,
):
    import asyncio
    from datetime import UTC, datetime, timedelta

    from app.access.limits import charge

    scoped = replace(principal, unit_id=unit_id)
    environment = request.app.state.environment
    with api.repo.sessions.begin() as session:
        user, _, report = api.repo._case(session, scoped, case_id, lock=True)
        if report.withdrawn_at:
            raise HTTPException(409, "Withdrawn reports cannot start new provider work")
        latitude, longitude = report.reported_latitude, report.reported_longitude
        charge(
            session,
            scope=user.id,
            rule="REVIEW_LIVE_CONTEXT",
            period="hour",
            maximum=api.repo.limits.context_per_hour,
        )
        cost = (
            int(environment.providers["air_quality"].configured)
            + int(environment.providers["weather"].configured)
            + 2 * int(environment.forecast.configured)
        )
        for _ in range(cost):
            charge(
                session,
                scope="global",
                rule="PAID_ANALYSIS",
                period="day",
                maximum=api.repo.limits.provider_calls_per_day,
            )
        api.access._audit(session, user.id, None, unit_id, "LIVE_CONTEXT_REQUESTED")
    try:
        async with asyncio.timeout(45):
            aq, weather = await asyncio.gather(
                environment.resident_source("air_quality", latitude, longitude),
                environment.resident_source("weather", latitude, longitude),
            )
            forecast = await environment.forecast_context(
                latitude, longitude, 24, current_result=aq
            )
    except TimeoutError as exc:
        raise HTTPException(
            503, "Optional live context timed out; saved review remains available"
        ) from exc
    with api.repo.sessions.begin() as session:
        api.repo._case(session, scoped, case_id)
    now = datetime.now(UTC)
    deadlines = [now + timedelta(seconds=900)]
    for item in (aq.data, weather.data):
        if item:
            deadlines.append(item.retrieved_at + timedelta(seconds=900))
    if forecast.retrieved_at:
        deadlines.append(forecast.retrieved_at + timedelta(seconds=900))
    return {
        "air_quality": aq.data,
        "weather": weather.data,
        "forecast": forecast,
        "sources": {"air_quality": aq.source, "weather": weather.source},
        "retrieved_at": now,
        "expires_at": min(deadlines),
    }
