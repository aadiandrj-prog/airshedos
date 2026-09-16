from fastapi import APIRouter, HTTPException, Request

from app.review.models import CaseSummary, OfficerCase, ReviewRequest
from app.review.repository import ReviewConflict

router = APIRouter(prefix="/api/v1/review/cases", tags=["Officer review"])
MISSING = "Case expired or unavailable. Submit and corroborate a new report."


@router.get("", response_model=list[CaseSummary])
async def cases(request: Request):
    return request.app.state.officer_cases.summaries()


@router.get("/{case_id}", response_model=OfficerCase)
async def case(case_id: str, request: Request):
    item = request.app.state.officer_cases.get(case_id)
    if item is None:
        raise HTTPException(404, MISSING)
    return item


@router.post("/{case_id}/review", response_model=OfficerCase)
async def review(case_id: str, body: ReviewRequest, request: Request):
    try:
        return request.app.state.officer_cases.transition(case_id, body)
    except KeyError as exc:
        raise HTTPException(404, MISSING) from exc
    except ReviewConflict as exc:
        raise HTTPException(409, str(exc)) from exc
