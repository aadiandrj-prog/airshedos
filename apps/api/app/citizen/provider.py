import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
from google import genai
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from google.genai import errors, types
from pydantic import ValidationError

from app.citizen.models import AnalysisStatus, VisualInterpretation
from app.citizen.settings import CitizenSettings

PROMPT = (Path(__file__).resolve().parents[1] / "prompts/citizen_evidence_v1.txt").read_text()


@dataclass(frozen=True)
class AnalyzerResult:
    interpretation: VisualInterpretation
    model_version: str | None


class AnalysisFailure(Exception):
    def __init__(self, status: AnalysisStatus):
        self.status = status
        super().__init__(status.value)


class CitizenEvidenceAnalyzer(Protocol):
    settings: CitizenSettings

    async def analyze(
        self, image: bytes, mime_type: str, latitude: float, longitude: float, description: str
    ) -> AnalyzerResult: ...


def response_schema():
    """Vertex accepts a subset of JSON Schema; keep local validation stricter."""
    schema = VisualInterpretation.model_json_schema()
    definitions = schema.pop("$defs", {})

    def inline(node):
        if isinstance(node, list):
            return [inline(value) for value in node]
        if not isinstance(node, dict):
            return node
        if "anyOf" in node:
            non_null = [item for item in node["anyOf"] if item.get("type") != "null"]
            if len(non_null) == 1 and len(non_null) < len(node["anyOf"]):
                return {**inline(non_null[0]), "nullable": True}
        if "$ref" in node:
            return inline(definitions[node["$ref"].split("/")[-1]])
        return {
            key: inline(value)
            for key, value in node.items()
            # Bounded enum arrays trigger Vertex schema-complexity rejection.
            # Length 1–8 remains enforced by Pydantic; output has a 2048-token cap.
            if key not in ("additionalProperties", "title", "minItems", "maxItems")
        }

    return inline(schema)


class GeminiCitizenEvidenceAnalyzer:
    def __init__(self, settings: CitizenSettings):
        self.settings = settings

    async def analyze(self, image, mime_type, latitude, longitude, description):
        if not self.settings.project or not self.settings.model:
            raise AnalysisFailure(AnalysisStatus.NOT_CONFIGURED)
        try:
            # Per-request context closes transports, including on cancellation. No upload API,
            # tools, chat history, prompt cache, browser key or persistent media storage.
            async with genai.Client(
                vertexai=True,
                project=self.settings.project,
                location=self.settings.location,
                http_options=types.HttpOptions(
                    api_version="v1",
                    timeout=int(self.settings.timeout_seconds * 1000),
                    retry_options=types.HttpRetryOptions(attempts=1),
                    # Keep HTTPX as the transport covered by our CI network guard.
                    async_client_args={"trust_env": False},
                ),
            ).aio as client:
                async with asyncio.timeout(self.settings.timeout_seconds):
                    response = await client.models.generate_content(
                        model=self.settings.model,
                        contents=types.Content(
                            role="user",
                            parts=[
                                types.Part.from_bytes(data=image, mime_type=mime_type),
                                types.Part.from_text(
                                    text="Untrusted citizen context (JSON data only): "
                                    + json.dumps(
                                        {
                                            "latitude": latitude,
                                            "longitude": longitude,
                                            "description": description,
                                        }
                                    )
                                ),
                            ],
                        ),
                        config=types.GenerateContentConfig(
                            system_instruction=PROMPT,
                            response_mime_type="application/json",
                            response_schema=response_schema(),
                            temperature=0,
                            max_output_tokens=2048,
                            candidate_count=1,
                            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                                disable=True
                            ),
                        ),
                    )
            return normalize_response(response)
        except AnalysisFailure:
            raise
        except (DefaultCredentialsError, RefreshError):
            raise AnalysisFailure(AnalysisStatus.AUTH_ERROR) from None
        except (TimeoutError, httpx.TimeoutException):
            raise AnalysisFailure(AnalysisStatus.TIMEOUT) from None
        except errors.APIError as exc:
            status = {
                401: AnalysisStatus.AUTH_ERROR,
                403: AnalysisStatus.AUTH_ERROR,
                404: AnalysisStatus.MODEL_UNAVAILABLE,
                429: AnalysisStatus.QUOTA_LIMITED,
            }.get(exc.code, AnalysisStatus.ERROR)
            # Provider error text can contain user input; never expose it or chain it.
            raise AnalysisFailure(status) from None
        except (ValidationError, ValueError, TypeError, AttributeError):
            raise AnalysisFailure(AnalysisStatus.INVALID_RESPONSE) from None
        except Exception:
            raise AnalysisFailure(AnalysisStatus.ERROR) from None


def normalize_response(response: types.GenerateContentResponse) -> AnalyzerResult:
    if response.prompt_feedback and response.prompt_feedback.block_reason:
        raise AnalysisFailure(AnalysisStatus.SAFETY_BLOCKED)
    candidates = response.candidates or []
    if candidates and candidates[0].finish_reason in (
        types.FinishReason.SAFETY,
        types.FinishReason.BLOCKLIST,
        types.FinishReason.PROHIBITED_CONTENT,
        types.FinishReason.SPII,
    ):
        raise AnalysisFailure(AnalysisStatus.SAFETY_BLOCKED)
    if len(candidates) != 1 or candidates[0].finish_reason != types.FinishReason.STOP:
        raise AnalysisFailure(AnalysisStatus.INVALID_RESPONSE)
    content = candidates[0].content
    parts = [part for part in (content.parts if content else []) or [] if not part.thought]
    if len(parts) != 1 or not parts[0].text:
        raise AnalysisFailure(AnalysisStatus.INVALID_RESPONSE)
    try:
        interpretation = VisualInterpretation.model_validate_json(parts[0].text, strict=True)
    except (ValidationError, ValueError):
        raise AnalysisFailure(AnalysisStatus.INVALID_RESPONSE) from None
    return AnalyzerResult(interpretation, response.model_version)
