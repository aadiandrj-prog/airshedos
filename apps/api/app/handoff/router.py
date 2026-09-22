from fastapi import APIRouter, HTTPException, Request, Response

from app.handoff.models import (
    CreateHandoff,
    HandoffJurisdiction,
    HandoffRecord,
    HandoffSummary,
    TransitionHandoff,
)
from app.handoff.repository import HandoffConflict

router = APIRouter(prefix="/api/v1", tags=["Simulated jurisdiction handoff"])


@router.post("/review/cases/{case_id}/handoffs", response_model=HandoffRecord, status_code=201)
async def create_handoff(case_id: str, body: CreateHandoff, request: Request):
    case = request.app.state.officer_cases.get(case_id)
    if case is None:
        raise HTTPException(404, "Source case expired or unavailable.")
    try:
        return request.app.state.handoffs.create(case, body)
    except HandoffConflict as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/handoffs", response_model=list[HandoffSummary])
async def list_handoffs(
    request: Request, case_id: str | None = None, destination: HandoffJurisdiction | None = None
):
    return request.app.state.handoffs.summaries(case_id, destination)


@router.get("/handoffs/{handoff_id}", response_model=HandoffRecord)
async def get_handoff(handoff_id: str, request: Request):
    try:
        return request.app.state.handoffs.get(handoff_id)
    except KeyError as exc:
        raise HTTPException(404, "Handoff expired or unavailable.") from exc


@router.post("/handoffs/{handoff_id}/transition", response_model=HandoffRecord)
async def transition_handoff(handoff_id: str, body: TransitionHandoff, request: Request):
    try:
        return request.app.state.handoffs.transition(handoff_id, body)
    except KeyError as exc:
        raise HTTPException(404, "Handoff expired or unavailable.") from exc
    except HandoffConflict as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get(
    "/handoffs/{handoff_id}/export",
    response_class=Response,
    responses={
        200: {
            "content": {"application/json": {}},
            "description": (
                "Exact canonical PollutionEvent UTF-8 bytes; SHA-256 in X-Payload-SHA256."
            ),
        }
    },
)
async def export_handoff(handoff_id: str, request: Request):
    try:
        data, digest, event_id, version = request.app.state.handoffs.export(handoff_id)
    except KeyError as exc:
        raise HTTPException(404, "Handoff expired or unavailable.") from exc
    except HandoffConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    return Response(
        content=data,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="pollution-event-{event_id}-v{version}.json"'
            ),
            "X-Payload-SHA256": digest,
            "Cache-Control": "no-store",
        },
    )
