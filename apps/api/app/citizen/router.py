import io
import warnings
from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from app.citizen.models import CitizenAnalysisResponse, CitizenInputError
from app.citizen.service import interpret

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_BODY_BYTES = MAX_IMAGE_BYTES + 64 * 1024
MAX_PIXELS = 16_000_000
PATH = "/api/v1/citizen-reports/analyze"
router = APIRouter(tags=["Citizen evidence"])


def invalid(message: str, code: int = 422):
    return JSONResponse(status_code=code, content=CitizenInputError(message=message).model_dump())


class CitizenUploadLimit:
    """Bound multipart bytes before parsing, including chunked/lying Content-Length uploads."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != PATH or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > MAX_BODY_BYTES:
                return await invalid("Upload exceeds the 5 MiB image request limit.", 413)(
                    scope, receive, send
                )
            if not message.get("more_body", False):
                break

        async def bounded_receive():
            nonlocal body
            if body is not None:
                data, body = bytes(body), None
                return {"type": "http.request", "body": data, "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)


def validated_image(data: bytes, mime_type: str) -> tuple[bytes, str]:
    """Decode and re-encode in memory; strip EXIF/GPS/text metadata before inference."""
    formats = {"image/jpeg": "JPEG", "image/png": "PNG"}
    if mime_type not in formats:
        raise ValueError("Use a JPEG or PNG image.")
    if not data:
        raise ValueError("Image is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds the 5 MiB limit.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as probe:
                if probe.format != formats[mime_type]:
                    raise ValueError("Image content does not match its declared MIME type.")
                if probe.width * probe.height > MAX_PIXELS or getattr(probe, "n_frames", 1) != 1:
                    raise ValueError("Use one still image with at most 16 million pixels.")
                probe.verify()
            with Image.open(io.BytesIO(data)) as original:
                original.load()
                image = ImageOps.exif_transpose(original).convert("RGB")
                # Limit provider bandwidth; this is image preprocessing, not scientific evidence.
                image.thumbnail((2048, 2048))
                clean = Image.new("RGB", image.size)
                clean.paste(image)
                output = io.BytesIO()
                clean.save(output, format="JPEG", quality=90)
                return output.getvalue(), "image/jpeg"
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValueError("Image cannot be decoded safely. Use a valid JPEG or PNG.") from exc


@router.post(
    PATH,
    response_model=CitizenAnalysisResponse,
    responses={413: {"model": CitizenInputError}, 422: {"model": CitizenInputError}},
)
async def analyze(
    request: Request,
    image: Annotated[UploadFile, File(description="One JPEG/PNG, maximum 5 MiB and 16 MP")],
    latitude: Annotated[float, Form(ge=-90, le=90, allow_inf_nan=False)],
    longitude: Annotated[float, Form(ge=-180, le=180, allow_inf_nan=False)],
    description: Annotated[str, Form(max_length=2000)] = "",
):
    try:
        form = await request.form()
        if (
            len(form.getlist("image")) != 1
            or set(form) - {"image", "latitude", "longitude", "description"}
            or any(len(form.getlist(key)) != 1 for key in form)
        ):
            return invalid("Submit exactly one image and the supported fields.")
        data = await image.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            return invalid("Image exceeds the 5 MiB limit.", 413)
        clean, mime_type = await run_in_threadpool(validated_image, data, image.content_type or "")
    except ValueError as exc:
        return invalid(str(exc))
    finally:
        await image.close()
    return await interpret(
        request.app.state.citizen_analyzer, clean, mime_type, latitude, longitude, description
    )
