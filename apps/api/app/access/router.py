from dataclasses import replace
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.access.contracts import (
    AuthorityList,
    MemberRead,
    MeRead,
    PilotCasePacket,
    ProposalCommand,
    ProposalRead,
    ResidentList,
    ReviewCommand,
)
from app.access.tokens import InvalidIdentity
from app.authority.contracts import AuthorityWorkspace
from app.authority.service import AuthorityService
from app.persistence.contracts import ResidentReportDetail

router = APIRouter(prefix="/api/v2", tags=["Pilot access"])
bearer = HTTPBearer(auto_error=False)


def actor(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    binding: Annotated[str | None, Header(alias="X-AirshedOS-Session")] = None,
):
    if credentials is None or credentials.scheme.lower() != "bearer" or not binding:
        raise HTTPException(401, "Sign in required", headers={"WWW-Authenticate": "Bearer"})
    service = request.app.state.access
    if service is None:
        raise HTTPException(503, "Identity service is not configured")
    try:
        return service.authenticate("Bearer " + credentials.credentials, binding)
    except InvalidIdentity as exc:
        raise HTTPException(
            401, "Sign in required", headers={"WWW-Authenticate": "Bearer"}
        ) from exc


Actor = Annotated[object, Depends(actor)]


@router.get("/me", response_model=MeRead)
def me(request: Request, principal: Actor):
    return request.app.state.access.me(principal)


@router.get("/resident/reports", response_model=ResidentList)
def reports(
    request: Request,
    principal: Actor,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0, le=1000),
):
    return request.app.state.access.reports(principal, limit=limit, offset=offset)


@router.get("/resident/reports/{report_id}", response_model=ResidentReportDetail)
def report(request: Request, principal: Actor, report_id: UUID):
    return request.app.state.access.repo.resident_detail(principal, report_id)


@router.get("/authority/units/{unit_id}/cases", response_model=AuthorityList)
def cases(
    request: Request,
    principal: Actor,
    unit_id: UUID,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0, le=1000),
    state: str | None = Query(
        None, pattern=r"^(NEW|UNDER_REVIEW|ACKNOWLEDGED|MONITORING|CLOSED_NO_ACTION)$"
    ),
    q: str | None = Query(None, min_length=1, max_length=100),
    assignment: str | None = Query(None, pattern=r"^(mine|unassigned)$"),
):
    return request.app.state.access.cases(
        principal, unit_id, limit=limit, offset=offset, state=state, query=q, assignment=assignment
    )


@router.get("/authority/units/{unit_id}/map")
def points(request: Request, principal: Actor, unit_id: UUID):
    return request.app.state.access.map_points(principal, unit_id)


@router.get("/authority/units/{unit_id}/cases/{case_id}", response_model=AuthorityWorkspace)
def case(request: Request, principal: Actor, unit_id: UUID, case_id: UUID):
    return AuthorityService(request.app.state.access).detail(
        replace(principal, unit_id=unit_id), case_id
    )


@router.post("/authority/units/{unit_id}/cases/{case_id}/review-events")
def review(request: Request, principal: Actor, unit_id: UUID, case_id: UUID, body: ReviewCommand):
    try:
        revision = AuthorityService(request.app.state.access).review(
            replace(principal, unit_id=unit_id),
            case_id,
            body,
        )
    except ValueError as exc:
        raise HTTPException(422, "Invalid review transition") from exc
    return {"revision": revision}


@router.get("/authority/units/{unit_id}/cases/{case_id}/export", response_model=PilotCasePacket)
def packet(request: Request, principal: Actor, unit_id: UUID, case_id: UUID):
    return request.app.state.access.packet(principal, unit_id, case_id)


@router.get("/resident/media/{media_id}")
def own_media(request: Request, principal: Actor, media_id: UUID):
    service = request.app.state.access
    if service.media is None:
        raise HTTPException(503, "Private media is not configured")
    return Response(
        service.media.read(principal, media_id),
        media_type="image/jpeg",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.get("/authority/units/{unit_id}/cases/{case_id}/media/{media_id}")
def case_media(request: Request, principal: Actor, unit_id: UUID, case_id: UUID, media_id: UUID):
    service = request.app.state.access
    if service.media is None:
        # Still check scope before configuration, so foreign object IDs reveal nothing.
        service.repo.authority_detail(replace(principal, unit_id=unit_id), case_id)
        raise HTTPException(503, "Private media is not configured")
    data = service.media.read(replace(principal, unit_id=unit_id), media_id, case_id=case_id)
    return Response(data, media_type="image/jpeg", headers={"X-Content-Type-Options": "nosniff"})


@router.get("/authority/units/{unit_id}/memberships", response_model=list[MemberRead])
def memberships(request: Request, principal: Actor, unit_id: UUID):
    return request.app.state.access.roster(principal, unit_id)


@router.post(
    "/authority/units/{unit_id}/membership-proposals", response_model=ProposalRead, status_code=201
)
def propose(request: Request, principal: Actor, unit_id: UUID, body: ProposalCommand):
    return request.app.state.access.propose(principal, unit_id, body.target_subject)


@router.post("/authority/units/{unit_id}/memberships/{membership_id}/suspend")
def suspend(request: Request, principal: Actor, unit_id: UUID, membership_id: UUID):
    request.app.state.access.suspend(principal, unit_id, membership_id)
    return JSONResponse({"status": "SUSPENDED"})
