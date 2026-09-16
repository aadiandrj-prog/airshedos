import asyncio
import base64
import io
import json
import logging
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from google.genai import errors, types
from PIL import Image

from app.citizen.models import (
    PROMPT_VERSION,
    AnalysisStatus,
    VisualInterpretation,
    VisualObservation,
    VisualUncertainty,
)
from app.citizen.provider import (
    AnalysisFailure,
    AnalyzerResult,
    GeminiCitizenEvidenceAnalyzer,
    normalize_response,
)
from app.citizen.router import MAX_BODY_BYTES, MAX_IMAGE_BYTES, PATH, validated_image
from app.citizen.settings import CitizenSettings
from app.main import create_app


@pytest.fixture
def output():
    return {
        "event_type": "uncertain",
        "event_type_confidence": "low",
        "visible_smoke": None,
        "visible_flames": False,
        "visible_dust": None,
        "industrial_context": None,
        "construction_context": False,
        "waste_burning_context": None,
        "vegetation_burning_context": None,
        "traffic_context": False,
        "scene_type": "outdoor",
        "apparent_scale": "unclear",
        "visual_observations": [VisualObservation.GRAY_PLUME.value],
        "uncertainty_reasons": [VisualUncertainty.HAZE_AMBIGUITY.value],
        "insufficient_evidence": True,
    }


def picture(fmt="PNG", size=(40, 40), **kwargs):
    buffer = io.BytesIO()
    Image.new("RGB", size, "gray").save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


class FakeAnalyzer:
    settings = CitizenSettings(model="fake-gemini", timeout_seconds=1)

    def __init__(self, output, failure=None):
        self.output = output
        self.failure = failure
        self.calls = []

    async def analyze(self, image, mime_type, latitude, longitude, description):
        self.calls.append((image, mime_type, latitude, longitude, description))
        if self.failure:
            raise AnalysisFailure(self.failure)
        return AnalyzerResult(VisualInterpretation.model_validate(self.output), "fake-version-001")


@pytest.fixture
def analyzer(output):
    return FakeAnalyzer(output)


@pytest.fixture
def client(analyzer):
    with TestClient(create_app(citizen_analyzer=analyzer)) as client:
        yield client


def submit(client, data=None, blob=None, mime="image/png"):
    return client.post(
        PATH,
        data=data
        if data is not None
        else {
            "latitude": "28.4595",
            "longitude": "77.0266",
            "description": "untrusted citizen text",
        },
        files={"image": ("not-trusted.extension", picture() if blob is None else blob, mime)},
    )


def test_valid_upload_distinct_report_derived_signal_and_provenance(client, analyzer):
    before = client.get("/api/v1/incidents").json()
    response = submit(client)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "interpreted"
    assert body["report"]["description"] == "untrusted citizen text"
    assert body["report"]["image_url"] is None
    assert body["report"]["language"] == "und"
    analysis = body["analysis"]
    assert analysis["event_type"] == "uncertain"
    assert analysis["event_type_confidence"] == "low"
    provenance = analysis["provenance"]
    assert provenance["source_report_id"] == body["report"]["id"]
    assert provenance["derived"] and provenance["author"] == "model"
    assert provenance["model"] == "fake-gemini"
    assert provenance["model_version"] == "fake-version-001"
    assert provenance["prompt_version"] == PROMPT_VERSION
    assert provenance["confidence_basis"] == "model_estimated_ordinal_not_calibrated"
    assert provenance["generated_at"] == analysis["analyzed_at"]
    assert not provenance["is_demo"]
    signal = body["evidence"]
    assert signal["status"] == "interpreted"
    assert signal["provenance"] == provenance
    assert signal["confidence"] is None and signal["observed_at"] is None
    assert signal["interpretation_at"] == analysis["analyzed_at"]
    assert "corroboration" in analysis["safety_note"]
    assert len(analyzer.calls) == 1
    assert client.get("/api/v1/incidents").json() == before


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"latitude": 28},
        {"latitude": 91, "longitude": 77},
        {"latitude": 28, "longitude": -181},
        {"latitude": "nan", "longitude": 0},
        {"latitude": 28, "longitude": "inf"},
        {"latitude": 1, "longitude": 1, "description": "x" * 2001},
    ],
)
def test_invalid_fields_are_sanitized(client, analyzer, data):
    response = submit(client, data=data)
    assert response.status_code == 422
    assert response.json()["status"] == "invalid_input"
    assert "x" * 2001 not in response.text
    assert not analyzer.calls


@pytest.mark.parametrize(
    "mime,blob",
    [
        ("text/plain", b"text"),
        ("image/webp", b"RIFF"),
        ("image/jpeg", picture()),
        ("image/png", b"not an image"),
        ("image/png", b""),
        ("image/png", picture()[:30]),
    ],
)
def test_invalid_images(client, analyzer, mime, blob):
    assert submit(client, mime=mime, blob=blob).status_code == 422
    assert not analyzer.calls


def test_missing_image(client):
    assert client.post(PATH, data={"latitude": 1, "longitude": 1}).status_code == 422


def test_multiple_images(client, analyzer):
    response = client.post(
        PATH,
        data={"latitude": 1, "longitude": 1},
        files=[
            ("image", ("one.png", picture(), "image/png")),
            ("image", ("two.png", picture(), "image/png")),
        ],
    )
    assert response.status_code == 422
    assert not analyzer.calls


@pytest.mark.parametrize("size", [MAX_IMAGE_BYTES + 1, MAX_BODY_BYTES + 1])
def test_oversized(client, analyzer, size):
    assert submit(client, blob=b"a" * size).status_code == 413
    assert not analyzer.calls


def test_chunked_body_limit_without_content_length(client):
    def chunks():
        for _ in range(100):
            yield b"x" * 65536

    assert (
        client.post(
            PATH, content=chunks(), headers={"Content-Type": "multipart/form-data; boundary=x"}
        ).status_code
        == 413
    )


def test_pixel_limit_and_animation():
    with pytest.raises(ValueError, match="16 million"):
        validated_image(picture(size=(4001, 4000)), "image/png")
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), "red").save(
        buffer, format="PNG", save_all=True, append_images=[Image.new("RGB", (2, 2), "blue")]
    )
    with pytest.raises(ValueError, match="still image"):
        validated_image(buffer.getvalue(), "image/png")


def test_strip_image_metadata_and_reorient():
    exif = Image.Exif()
    exif[270] = "private camera description"
    exif[274] = 6
    data, mime = validated_image(picture("JPEG", size=(60, 40), exif=exif), "image/jpeg")
    with Image.open(io.BytesIO(data)) as image:
        assert not image.getexif()
        assert image.size == (40, 60)
    assert mime == "image/jpeg"
    assert b"private camera description" not in data


def test_upload_closed_and_no_payload_logs(client, analyzer, monkeypatch, caplog):
    import starlette.formparsers

    monkeypatch.setattr(starlette.formparsers.MultiPartParser, "spool_max_size", 16)
    original = starlette.formparsers.SpooledTemporaryFile
    files = []

    def record(*args, **kwargs):
        obj = original(*args, **kwargs)
        files.append(obj)
        return obj

    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", record)
    with caplog.at_level(logging.INFO):
        response = submit(client)
    assert files and all(f.closed for f in files)
    assert all(f._rolled for f in files)
    assert base64.b64encode(picture()).decode() not in response.text + caplog.text
    assert "untrusted citizen text" not in caplog.text
    assert "event_class=uncertain" in caplog.text and "prompt_version=" in caplog.text
    assert "visible_smoke" not in caplog.text
    assert len(analyzer.calls) == 1


@pytest.mark.parametrize("status", [s for s in AnalysisStatus if s != AnalysisStatus.INTERPRETED])
def test_independent_failure_no_fabricated_evidence(client, analyzer, status):
    analyzer.failure = status
    body = submit(client).json()
    assert body["status"] == status.value
    assert body["analysis"] is None and body["evidence"] is None
    assert body["report"]["description"] == "untrusted citizen text"
    assert client.get("/ready").status_code == 200


def test_real_provider_unconfigured():
    with TestClient(create_app()) as client:
        assert submit(client).json()["status"] == "not_configured"


def test_service_deadline(client, analyzer):
    cancelled = []

    async def slow(*args):
        try:
            await asyncio.sleep(5)
        finally:
            cancelled.append(True)

    analyzer.analyze = slow
    response = submit(client).json()
    assert response["status"] == "timeout" and cancelled
    assert response["latency_ms"] < 2000


def sdk_response(output, finish="STOP", **kwargs):
    return types.GenerateContentResponse(
        model_version="model-001",
        candidates=[
            types.Candidate(
                finish_reason=finish,
                content=types.Content(parts=[types.Part(text=json.dumps(output))]),
            )
        ],
        **kwargs,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("event_type", "confirmed_toxic_gas"),
        ("event_type_confidence", 0.99),
        ("visible_smoke", "true"),
        ("visual_observations", ["Company X caused toxic pollution"]),
        ("uncertainty_reasons", []),
        ("event_type_confidence", "high"),
        ("event_type", "industrial_smoke"),
        ("event_type", "no_visible_pollution"),
        ("secret_extra", "forbidden"),
    ],
)
def test_schema_rejects_unsupported_claims(output, field, value):
    output[field] = value
    with pytest.raises(AnalysisFailure) as exc:
        normalize_response(sdk_response(output))
    assert exc.value.status == AnalysisStatus.INVALID_RESPONSE


@pytest.mark.parametrize("finish", ["SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"])
def test_safety_finish(output, finish):
    with pytest.raises(AnalysisFailure) as exc:
        normalize_response(sdk_response(output, finish))
    assert exc.value.status == AnalysisStatus.SAFETY_BLOCKED


@pytest.mark.parametrize(
    "response",
    [
        types.GenerateContentResponse(),
        types.GenerateContentResponse(
            prompt_feedback=types.GenerateContentResponsePromptFeedback(block_reason="SAFETY")
        ),
        types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    finish_reason="STOP", content=types.Content(parts=[types.Part(text="not JSON")])
                )
            ]
        ),
    ],
)
def test_missing_malformed_blocked_response(response):
    with pytest.raises(AnalysisFailure):
        normalize_response(response)


def test_normalization(output):
    result = normalize_response(sdk_response(output))
    assert result.model_version == "model-001"
    assert result.interpretation.event_type == "uncertain"


@pytest.fixture
def sdk(monkeypatch, output):
    state = SimpleNamespace(calls=[], constructor=[], fail=None, closed=False)

    class Client:
        def __init__(self, **kwargs):
            state.constructor.append(kwargs)
            self.aio = self
            self.models = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            state.closed = True

        async def generate_content(self, **kwargs):
            state.calls.append(kwargs)
            if state.fail:
                raise state.fail
            return sdk_response(output)

    monkeypatch.setattr("app.citizen.provider.genai.Client", Client)
    return state


@pytest.mark.anyio
async def test_vertex_structured_multimodal_contract(sdk):
    provider = GeminiCitizenEvidenceAnalyzer(CitizenSettings(project="test-project"))
    result = await provider.analyze(picture(), "image/png", 28.4, 77, "Factory releasing toxic gas")
    assert result.interpretation.event_type == "uncertain"
    assert sdk.constructor[0]["vertexai"] is True
    assert sdk.constructor[0]["http_options"].retry_options.attempts == 1
    call = sdk.calls[0]
    assert call["contents"].parts[0].inline_data.data == picture()
    assert "Factory releasing toxic gas" in call["contents"].parts[1].text
    config = call["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema["properties"]["event_type"]["enum"]
    assert config.response_schema["properties"]["visible_smoke"] == {
        "type": "boolean",
        "nullable": True,
    }
    assert "additionalProperties" not in json.dumps(config.response_schema)
    assert "maxItems" not in json.dumps(config.response_schema)
    assert "minItems" not in json.dumps(config.response_schema)
    assert config.automatic_function_calling.disable and not config.tools
    assert "untrusted" in config.system_instruction
    assert sdk.closed and len(sdk.calls) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    "exception,status",
    [
        (DefaultCredentialsError("private"), "auth_error"),
        (RefreshError("private"), "auth_error"),
        (TimeoutError("private"), "timeout"),
        (errors.ClientError(403, {"error": {"message": "private"}}), "auth_error"),
        (errors.ClientError(404, {"error": {"message": "private"}}), "model_unavailable"),
        (errors.ClientError(429, {"error": {"message": "private"}}), "quota_limited"),
        (errors.ServerError(503, {"error": {"message": "private"}}), "error"),
        (ValueError("private"), "invalid_response"),
        (RuntimeError("private"), "error"),
    ],
)
async def test_provider_error_mapping_no_retry_or_leak(sdk, exception, status):
    sdk.fail = exception
    provider = GeminiCitizenEvidenceAnalyzer(CitizenSettings(project="test-project"))
    with pytest.raises(AnalysisFailure) as exc:
        await provider.analyze(picture(), "image/png", 1, 1, "private text")
    assert exc.value.status == status
    assert "private" not in str(exc.value)
    assert len(sdk.calls) == 1 and sdk.closed


def test_openapi_upload_and_derived_contract(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"][PATH]["post"]
    assert "multipart/form-data" in operation["requestBody"]["content"]
    for name in (
        "VisualConfidence",
        "GeminiEvidenceAnalysis",
        "CitizenVisualSignal",
        "ModelProvenance",
    ):
        assert name in schema["components"]["schemas"]
    assert "422" in operation["responses"] and "413" in operation["responses"]


# Prompt/category smoke fixtures only; these tests do not measure model accuracy.
@pytest.mark.parametrize(
    "case,event,insufficient",
    [
        ("obvious burning", "open_burning", False),
        ("distant plume", "uncertain", True),
        ("construction dust", "construction_dust", False),
        ("traffic haze", "uncertain", True),
        ("cloud/fog", "uncertain", True),
        ("clean street", "no_visible_pollution", False),
        ("night", "uncertain", True),
        ("blurry", "uncertain", True),
        ("indoor", "no_visible_pollution", False),
        ("misleading description", "uncertain", True),
    ],
)
def test_critical_case_contracts(output, case, event, insufficient):
    output.update(event_type=event, insufficient_evidence=insufficient)
    assert VisualInterpretation.model_validate(output).event_type == event


def test_citizen_endpoint_never_queries_environment(client, monkeypatch):
    calls = []

    async def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("Citizen intake must not query environmental sources")

    monkeypatch.setattr(client.app.state.environment, "context", forbidden)
    monkeypatch.setattr(client.app.state.environment, "satellite_context", forbidden)
    assert submit(client).json()["status"] == "interpreted"
    assert not calls


def test_local_array_bounds_still_apply(output):
    output["visual_observations"] *= 9
    with pytest.raises(AnalysisFailure) as exc:
        normalize_response(sdk_response(output))
    assert exc.value.status == AnalysisStatus.INVALID_RESPONSE


def test_unknown_multipart_field_rejected(client, analyzer):
    response = submit(client, data={"latitude": 1, "longitude": 1, "unexpected": "unused"})
    assert response.status_code == 422
    assert not analyzer.calls
