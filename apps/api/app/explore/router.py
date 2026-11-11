import os
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from app.explore.service import AREAS, Area, Overview, OverviewService
from app.persistence.contracts import RateLimited, StrictModel

router = APIRouter(prefix="/api/v2/explore", tags=["Public area overview"])


class OverviewRequest(StrictModel):
    pass


@router.get("/areas", response_model=list[Area])
def areas(request: Request):
    if request.query_params:
        raise HTTPException(422, "No query parameters are supported")
    return list(AREAS.values())


@router.post("/areas/{area_id}/overview", response_model=Overview)
async def overview(request: Request, area_id: str, body: Annotated[OverviewRequest, Body()]):
    if area_id not in AREAS:
        raise HTTPException(404, "Area not supported")
    if request.query_params:
        raise HTTPException(422, "No query parameters are supported")
    if os.getenv("PUBLIC_OVERVIEW_ENABLED") != "1" or request.app.state.mode != "pilot":
        raise HTTPException(503, "Area overview is not enabled yet")
    if request.app.state.access is None:
        raise HTTPException(503, "Overview admission is unavailable")
    service = getattr(request.app.state, "public_overview", None)
    if service is None:
        try:
            daily = int(os.getenv("PUBLIC_OVERVIEW_HTTP_PER_DAY", "100"))
            hourly = int(os.getenv("PUBLIC_OVERVIEW_REQUESTS_PER_HOUR", "120"))
            if not 0 <= daily <= 1000 or not 0 <= hourly <= 1000:
                raise ValueError()
            service = OverviewService(
                request.app.state.environment,
                request.app.state.access.repo,
                daily_limit=daily,
                requests_per_hour=hourly,
            )
        except (ValueError, TypeError):
            raise HTTPException(503, "Overview configuration unavailable") from None
        request.app.state.public_overview = service
    try:
        return await service.overview(area_id)
    except RateLimited:
        raise HTTPException(429, "Overview request limit reached. Try later.") from None
    except SQLAlchemyError:
        raise HTTPException(503, "Overview admission is temporarily unavailable") from None


class PublicOverviewBodyLimit:
    """Bound anonymous JSON parsing, including chunked requests without Content-Length."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if not (
            scope["type"] == "http"
            and scope["path"].startswith("/api/v2/explore/")
            and scope["method"] == "POST"
        ):
            return await self.app(scope, receive, send)
        import asyncio

        from fastapi.responses import JSONResponse

        async def reject(status):
            return await JSONResponse(
                {"detail": "Bounded empty JSON object required"},
                status_code=status,
                headers={"Cache-Control": "private, no-store"},
            )(scope, receive, send)

        body = bytearray()
        try:
            async with asyncio.timeout(5):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > 128:
                        return await reject(413)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            return await reject(408)

        async def bounded_receive():
            nonlocal body
            if body is not None:
                data, body = bytes(body), None
                return {"type": "http.request", "body": data, "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
