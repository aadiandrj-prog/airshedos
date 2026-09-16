# Phase 2A — citizen evidence and Gemini verification

Verified locally on **13 September 2026 IST** (live artifact timestamps are UTC). Scope stops at citizen intake and independent visual interpretation. No Phase 2B work, environmental fusion, source attribution, operational incident scoring, forecasting, Maps, accounts, notifications or persistent media storage was introduced.

## Implementation and baseline

With explicit user approval, verified Phase 1B PR #1 and Phase 1C PR #2 were merged. Phase 2A starts from merged `main` commit `263d65a`, on `codex/phase-2a-citizen-evidence`. Existing environmental adapters, Sentinel-5P QA predicates, cache logic and scientific units were not changed. A new `interpreted` evidence status permits unknown image capture time and forbids an incident confidence score.

`POST /api/v1/citizen-reports/analyze` accepts one multipart image, latitude, longitude and optional description. Human `CitizenReport`, derived `GeminiEvidenceAnalysis` and normalized `CitizenVisualSignal` stay distinct. Model provenance records report ID, configured model, returned model version, prompt version, analysis time, derived/model authorship and ordinal confidence basis. No report is added to the fictional incident repository; no environmental query occurs from intake.

The frontend's **SUBMIT FIELD EVIDENCE** panel preserves the dark-green visual language and source-state badges. It supports preview, validation, loading, retry and clear. Citizen text is explicitly unverified and separate from **AI INTERPRETATION**. Event types are possible interpretations; confidence is low/medium/high, model-estimated and uncalibrated. Fixed copy says: **“AI interpretation — requires environmental corroboration.”** This is not incident truth, severity, source causality or an AQ measurement.

## Authentication, model and prompt

- Official `google-genai==2.23.0`, explicitly `vertexai=True`, API `v1`.
- Existing Google Cloud project `airshedos`, existing backend Application Default Credentials; no service account, long-lived key or IAM-role change was introduced.
- `aiplatform.googleapis.com` initially returned HTTP 403 `SERVICE_DISABLED`. It was enabled in the existing project, resolving the access blocker.
- `GEMINI_MODEL=gemini-3.1-flash-lite`, `GOOGLE_CLOUD_LOCATION=global`; configurable defaults when these fields are empty. `GOOGLE_CLOUD_PROJECT` is shared with the established setup. The returned model version was `gemini-3.1-flash-lite`; no unpublished weight/snapshot version is invented.
- Prompt: `app/prompts/citizen_evidence_v1.txt`. Final prompt SHA-256 is recorded in the final live artifact. It treats image/text as untrusted context, prohibits identity/source/enforcement/AQ claims, distinguishes visible observations from tentative interpretation, and requires uncertainty for weak evidence.
- Schema constrains event taxonomy, ordinal confidence, nullable feature/context booleans, scene/scale and controlled observation/uncertainty statements. There is no arbitrary model-generated prose, identity, pollutant concentration or probability field. Strict local validation also enforces array length 1–8, booleans, extra-field rejection and insufficient-evidence consistency.

### Diagnosed failures, not hidden retries

1. API disabled: all five initial requests returned safe `auth_error` responses with no analysis. The provider error was independently inspected, then the API enabled.
2. Remote schema: minimal/schema-small requests succeeded, while the full schema returned HTTP 400. Isolated calls showed that removing remote array-length bounds resolved this particular complexity rejection; removing nullable alone did not. The final wire schema retains the complete field/enum contract and uses documented `nullable` booleans. Length constraints remain unchanged in Pydantic and a 2,048-token output cap remains. See [Google's schema-complexity guidance](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/control-generated-output).
3. Pre-release prompt: the first compatible full image run returned four valid results and rejected the indoor image. A sanitized follow-up found `no_visible_pollution`, `high`, `insufficient_evidence=true`: an inconsistent combination. The original rejection rule was retained. The prompt/field description were clarified: insufficient evidence means inability to choose a visual category, not absence of pollution features; a clearly clean indoor scene may use `no_visible_pollution` with that flag false. [The initial 4/5 result is preserved](verification/phase2a-gemini-initial.json). No model output was repaired or relabeled server-side.

These were separate manual diagnostics and a targeted prompt correction. Runtime requests still make **one attempt**, including on schema/safety failures. No scientific QA thresholds or satellite defaults changed.

## Final genuine Vertex evaluation

[Final structured artifact](verification/phase2a-gemini-live.json), generated **2026-09-12 22:58:27 UTC / 13 September 04:28:27 IST**. Five synthetic, locally maintained images; fixed coordinate inputs 28.4595, 77.0266 do not assert image geolocation. Calls went through the actual multipart API in an in-process HTTP test client and then real Vertex; no environmental endpoint was invoked.

| Synthetic case | Possible event returned | Ordinal confidence | Inference/service latency | Strict schema |
| --- | --- | --- | --- | --- |
| Visible open burning | `open_burning` | high | 5,112.87 ms | pass |
| Distant ambiguous plume | `uncertain` | low | 3,708.72 ms | pass |
| Construction dust | `construction_dust` | high | 3,151.41 ms | pass |
| Fog + “Factory releasing toxic gas” | `uncertain` | low | 2,748.49 ms | pass |
| Clean indoor room | `no_visible_pollution` | high | 2,710.68 ms | pass |

**5/5 schema-valid; 5/5 within declared broad expected categories; manual evaluation exit 0.** Both ambiguous scenes used `uncertain`. The misleading-description case explicitly included “Citizen description is unverified context, not visual evidence.” These results are a small synthetic smoke-test, not calibrated accuracy or a scientific benchmark. Timings start after upload validation and exclude browser upload/download time.

Example sanitized interpretation of the misleading fog image:

```json
{
  "event_type": "uncertain",
  "event_type_confidence": "low",
  "insufficient_evidence": true,
  "uncertainty_reasons": [
    "Smoke, dust, cloud and fog can look similar.",
    "Citizen description is unverified context, not visual evidence.",
    "Image alone cannot establish source or pollutant type.",
    "No clear pollution-related event can be inferred from this image."
  ]
}
```

An additional real browser → Docker API → Vertex submission of the synthetic fog image is recorded in [the browser artifact](verification/phase2a-live-browser.json). Environmental cards were mocked in that UI check to isolate submission. The standalone environmental gate below was fully live. [Desktop](screenshots/phase2a-live-desktop.png) and [mobile](screenshots/phase2a-live-mobile.png) screenshots show the real Gemini result, not a fake-model response.

## Privacy, limits and failures

JPEG/PNG only; 5 MiB maximum, 16 million decoded pixels, one still frame; description up to 2,000 characters. A scoped ASGI limiter enforces actual request bytes before parsing, even with chunked or misleading Content-Length. Actual content format and decodability are checked. Preprocessing orients and re-encodes a metadata-free JPEG, at most 2048 pixels per edge, in memory. Original multipart uploads over 1 MiB may spool temporarily; they are explicitly closed before inference and closed by FastAPI on input validation errors. Tests force disk spooling and verify file closure. No persistent images, image URLs, upload history, reports or analysis cache are created. Browser object URLs are revoked on clear/replacement/unmount. Cloud processing is governed by Google's policies; the app does not promise zero cloud-side retention.

Missing project returns `not_configured` without SDK initialization. ADC/permission/API errors, unavailable model, quota, timeout, safety blocks, invalid structured output and generic errors return distinct safe statuses and null analysis/evidence. No startup dependency on Gemini authentication. A valid submission with provider failure returns HTTP 200, invalid fields/image 422, oversized upload 413. SDK and service deadlines default to 30 seconds, maximum configurable 60; no automatic retry or tools/function calls. Logs contain request ID, model, prompt version, status, event class and latency only, not raw images, descriptions, responses or provider error bodies.

## Automated and deployment checks

| Check | Final local result |
| --- | --- |
| Full backend tests | **215 passed, 2 existing deprecation warnings, 11.10 s** |
| Existing Phase 1 regression coverage | All original **142** tests retained and passing |
| New citizen tests | **73** passing, included in full suite |
| Backend lint / format | `ruff check`: pass; `ruff format --check`: 30 files formatted |
| Full Chromium browser suite | **19 passed, 16.6 s** (13 existing + 6 new) |
| Frontend lint / typecheck | pass |
| Frontend production build | pass, Next.js 16.3.4, all static pages generated |
| OpenAPI / generated TypeScript | re-export and regeneration byte-consistent |
| Docker | both images built; API and web started and **healthy**; non-root API can read existing ADC via the established read-only mount |
| Secret scan | source + generated frontend build + verification artifacts: **pass, 0 findings** |
| Git whitespace/diff check | pass |

The existing two backend warnings concern Starlette's HTTPX test-client integration and AnyIO's old BlockingPortal alias. No tests were weakened. CI receives no Gemini credentials; HTTPX (sync/async), requests and existing Earth Engine transports are blocked in unit tests. Provider fakes and synthetic browser routes cover successful/uncertain responses and input, model, timeout, quota, safety, schema and privacy failures. The live evaluation is manual-only and outside test discovery.

The final PR's GitHub Checks tab is authoritative for remote CI; the completion report records its observed result. Phase 2A is not merged automatically.

## Separate Phase 1 live regression

[Authenticated Gurugram regression artifact](verification/phase2a-environment-regression.json): Google AQ, Google Weather, NASA FIRMS and Earth Engine/Sentinel-5P all passed. Ground cache reuse and partial provider failure passed; satellite cache reuse and gate passed. Timings: AQ 1,736.19 ms, Weather 1,413.41 ms, FIRMS 1,361.58 ms, satellite batch 14,061.35 ms; cached satellite 0.82 ms. This remains an independent diagnostic, not image corroboration.

## Limits and deviations

- Five maintained synthetic images instead of the aspirational 20–30-image set, using the brief's explicit small-subset allowance. Ten critical category contracts are mocked in CI; live accuracy on traffic haze, night, blur and diverse real street scenes is **not established**. [Fixture provenance and exact generation prompts](../apps/api/scripts/citizen-evaluation/README.md) are included; built-in image generation was used, with assets saved in that directory.
- Controlled observation/uncertainty statements replace open-ended model prose to prevent arbitrary attribution/identity/toxicity claims from reaching the product. This is intentionally less expressive. The model can still misclassify visible features; enum constraints do not establish truth.
- `observed_at` stays null because upload time is not capture time; interpretation/upload times are separately preserved. No calibrated confidence score is fabricated.
- No WebP, persistent storage, Cloud Storage, reports listing or analysis cache; resubmission creates another model request. Returned model version is only as specific as the provider supplies.
- Global model location is configurable; production identity, access/admission controls, retention requirements and a reviewed real-image evaluation set need a separate decision before public deployment.

Recommendation: review and merge Phase 2A after green CI. Scope Phase 2B explicitly around joining independently timestamped evidence with missing/conflicting-source handling and transparent corroboration rules. Do not infer source causality from these image labels. **Stop after Phase 2A.**
