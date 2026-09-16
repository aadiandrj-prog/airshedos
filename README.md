# AirshedOS

**AI Pollution Incident Command — Phase 3A spatial officer workflow; Phase 2D custom model rejected.**

Indian cities receive fragmented citizen, air-quality, fire, weather, and satellite signals. AirshedOS is an incident command concept for combining that evidence, communicating uncertainty, and coordinating a response across jurisdictions.

The command center preserves **one fictional Delhi–Gurugram-border incident**, served by FastAPI to a Next.js command center. It includes evidence provenance, an illustrative six-hour risk forecast, acknowledgment, and simulated jurisdiction sharing. **This incident remains a demo.** A separate coordinate probe now retrieves current Google Air Quality, Google Weather, and NASA FIRMS context through backend adapters, plus latest usable Sentinel-5P NO₂, CO and UV Aerosol Index evidence through Google Earth Engine. Missing keys produce explicit `not_configured` states; no substitute readings are shown. A separate citizen intake panel now sends one image and context to Vertex AI Gemini for a structured visual interpretation. An explicit corroboration step now joins the server-owned interpretation with environmental context through a deterministic checklist. It creates an advisory assessment, not an incident. Real notifications remain unimplemented.

Phase 2C adds a separate historical dataset pipeline for OpenAQ and ERA5-Land. **Real acceptance built five coverage-selected stations over 316 days, with 8,926 complete operational rows and a separate research frame.** Its default operational profile uses a configurable AQ availability buffer and excludes ERA5. A separate research profile is explicitly not deployment-safe. Historical publication times and revisions remain unverified; buffered availability is a conditional contract. Phase 2D evaluated Ridge, histogram gradient boosting and XGBoost, but **MODEL_NOT_ACCEPTED**: none passed the October baseline gate. The final test period remains untouched by candidate evaluation; no model is integrated or deployed. See [the model protocol](docs/PREDICTION_MODEL.md) and [Phase 2D results](docs/PHASE_2D_VERIFICATION.md). See [the data contract](docs/PREDICTION_DATASET.md) and [verification report](docs/PHASE_2C_VERIFICATION.md).

Phase 2E adds a separately labelled **Google Air Quality forecast outlook** for the next 6, 12 and 24 hours, both in the coordinate probe and after citizen corroboration. It preserves CPCB index identity, native pollutant units and provenance. Forecast values never increase corroboration support. The custom model remains rejected and undeployed. See [forecast rules and API](docs/FORECASTING.md) and [Phase 2E verification](docs/PHASE_2E_VERIFICATION.md).

Phase 3A adds a selected-case Google Map, a deterministic case queue, prototype jurisdiction labels and ephemeral manual officer review. Evidence, corroboration and Google forecast snapshots cannot be edited by review actions. A separate restricted browser key enables Maps; map failure leaves the textual workflow usable. See [the command-center guide](docs/COMMAND_CENTER.md) and [Phase 3A verification](docs/PHASE_3A_VERIFICATION.md).

## Current architecture

```text
Demo fixture → In-memory repository → FastAPI REST API → Next.js command center
                                         ↑                    ↓
                                   Officer actions ← Acknowledge / simulate share
```

The Python API owns incident data and behavior. Pydantic generates OpenAPI; frontend domain types are generated from that contract. The browser fetches the API directly. Next.js does not duplicate the incident fixture. No database, queue, or login is needed. The demo and configuration states work without keys; real provider readings require backend credentials.

## Repository

```text
apps/
  api/
    app/                  # Models, fictional fixture, repository, routes, environment adapters
    prediction/           # Offline historical research frame; never imported by FastAPI
    tests/                # Endpoint, schema, state, and concurrency tests
    scripts/              # OpenAPI export, manual verification and synthetic image evaluation
    openapi.json          # Generated API contract
    pyproject.toml
    requirements*.lock    # Exact Python dependency versions
    Dockerfile
  web/
    src/app/              # Single command-center page and responsive styles
    src/components/       # Operational map, evidence, forecast and officer review
    src/lib/              # API client and generated domain types
    e2e/                  # Browser checks against the running API
    package.json
    package-lock.json
    Dockerfile
docs/
  ARCHITECTURE.md
  VERIFICATION.md         # Historical Phase 1A result
  PHASE_1B_VERIFICATION.md
  PHASE_1C_VERIFICATION.md
  PHASE_2A_VERIFICATION.md
  PHASE_2B_VERIFICATION.md
  PHASE_2C_VERIFICATION.md
  PREDICTION_DATASET.md
  CORROBORATION_RULES.md
  DATA_SOURCES.md
  screenshots/
.github/workflows/ci.yml
.env.example
docker-compose.yml
```

## Run locally

Prerequisites: **Node.js 22 or newer**, npm, **Python 3.12 or newer** (3.13 recommended). Use one backend worker: state is process-local.

Terminal 1, from the repository root:

```sh
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock -r requirements-dataset.lock
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

On Windows, activate with `.venv\Scripts\activate`.

Terminal 2, from the repository root:

```sh
cp apps/web/.env.example apps/web/.env.local
cd apps/web
npm install
npm run dev
```

Open [the command center](http://localhost:3000) and [interactive API docs](http://localhost:8000/docs). The default API URL works without creating an environment file. Ground-source and incident UI timestamps use IST; satellite timestamps use explicitly labelled UTC. API timestamps include a timezone.

For live providers, copy root `.env.example` to root `.env`, set `GOOGLE_MAPS_PLATFORM_API_KEY` and `NASA_FIRMS_MAP_KEY`, then add `--env-file ../../.env` to the backend command above. Enable Google Air Quality and Weather for the key. See [data sources](docs/DATA_SOURCES.md). **Never copy backend keys into the frontend directory.** Next.js reads only `apps/web/.env.local`; Compose and the manual verification script read root `.env`. Without an env file, backend settings come from the shell. Set `CORS_ORIGINS` when using a different browser origin, for example:

```sh
CORS_ORIGINS=http://localhost:3001 uvicorn app.main:app --port 8000
```

`NEXT_PUBLIC_API_BASE_URL` is public browser configuration, never a place for secrets. It is compiled into production builds; rebuild when changing it.

## Docker

From the root, with Docker Desktop/Engine and Compose available:

```sh
docker compose up --build -d --wait
docker compose ps
docker compose down
```

The frontend is at [localhost:3000](http://localhost:3000); API at [localhost:8000](http://localhost:8000). Only two containers run. Both have health checks and non-root users. Ports bind to loopback. No cloud credentials or persistent volumes are required. Compose optionally reads a root `.env` copied from `.env.example`.

The browser accesses `localhost:8000`, **not** the Docker service name `api`. If ports are occupied, use consistent overrides:

```sh
API_PORT=8001 WEB_PORT=3001 NEXT_PUBLIC_API_BASE_URL=http://localhost:8001 CORS_ORIGINS=http://localhost:3001 docker compose up --build -d --wait
```

## API routes

| Method | Route | Result |
| --- | --- | --- |
| GET | `/health` | `{"status":"ok"}` |
| GET | `/ready` | Readiness, in-memory storage, demo mode |
| GET | `/api/v1/incidents` | Incident list |
| GET | `/api/v1/incidents/{incident_id}` | Evidence, forecast, reports, jurisdiction, actions |
| POST | `/api/v1/incidents/{incident_id}/acknowledge` | Updated incident; repeated calls do not duplicate actions |
| POST | `/api/v1/incidents/{incident_id}/share` | Simulated result, action, and updated incident |
| GET | `/api/v1/environment/context?lat=28.4595&lng=77.0266` | Independent normalized current environmental context, including partial failures |
| GET | `/api/v1/environment/satellite?lat=28.4595&lng=77.0266` | Latest usable satellite observations, product availability, QA and provenance |
| GET | `/api/v1/environment/sources` | Configuration state only; no provider request or credentials |
| GET | `/openapi.json` | Machine-readable API contract |
| GET | `/docs` | Swagger UI |

Example:

```sh
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/incidents/AS-DEL-001
curl -X POST http://localhost:8000/api/v1/incidents/AS-DEL-001/acknowledge
curl -X POST http://localhost:8000/api/v1/incidents/AS-DEL-001/share \
  -H 'Content-Type: application/json' \
  -d '{"target_jurisdiction_id":"south-west-delhi"}'
```

Missing incidents return 404. Missing/invalid/extra share fields or a target outside the affected jurisdictions return 422. The owning jurisdiction is not a share target. Repeated sharing to the same jurisdiction returns the existing simulated action. Acknowledgment does not resolve an incident or remove its priority.

## Quality checks

Backend, from `apps/api` with the virtual environment activated:

```sh
ruff check .
ruff format --check .
pytest -q
python scripts/export_openapi.py
```

Frontend, from `apps/web`:

```sh
npm ci
npm run generate:api
npm run lint
npm run typecheck
npm run build
```

After model changes, regenerate both OpenAPI and TypeScript definitions and commit them together. CI detects stale generated files. Backend, frontend, browser/Docker and secret checks run on every push and pull request.

Browser checks require both apps running, ideally after a fresh backend start so the first test exercises both mutations:

```sh
cd apps/web
npx playwright install chromium
npm run test:e2e
```

These checks cover real API connectivity/actions, reload behavior, evidence, desktop/mobile screenshots, connection failure, loading, empty state, and failed actions. Browser regression screenshots are saved under ignored `apps/web/test-results`; curated verification captures are under `docs/screenshots`. Environmental display tests also intercept explicitly synthetic provider fixtures to verify readings, units, cached states, partial responses, and zero detections; these are not live integration evidence. CI also runs browser checks against credential-free Docker containers and runs the repository secret scanner.

## Data and limitations

- The incident workspace’s environmental values, locations, evidence scores, and forecasts are hand-authored fixtures. The fixed scenario date is 10 September 2026; it does not refresh to masquerade as a live observation.
- Confidence and probabilities use 0–1 in the API and percentages in the UI. The 86% confidence and 81% spike risk are illustrative, not calibrated model outputs.
- The fictional incident’s satellite evidence remains unavailable. The independent satellite probe can retrieve real regional observations; it never changes the demo incident or assigns confidence.
- State resets when the API restarts, including on development reload. A single process is required; there is no persistence or multi-worker coordination.
- Acknowledgment is stored locally. Sharing records a simulation and sends nothing externally.
- The selected-workflow map shows coordinates and returned FIRMS detections, not pollution causality. Prototype jurisdiction areas are not official boundaries.
- Environmental providers are independent of incident evidence. They do not alter demo confidence, forecasts, or actions. The probe fetches on page load and on **Check conditions**; there is no background monitoring.
- Provider outages and missing credentials are expected. FIRMS `null` means unavailable; an empty list means a valid query returned zero nearby detections.
- Optional timezone-aware `at` remains reference metadata for AQ/weather/FIRMS, which still query current conditions. For satellite only, it specifies the exclusive search-window end.
- No authentication, production deployment, historical storage, or automatic attribution is included.

## Planned architecture (not implemented)

Phase 3A provides spatial presentation and temporary manual review. Durable records, accounts and real jurisdiction interoperability require separate later phases.

Current: Google AQ, Weather, FIRMS, Sentinel-5P, Gemini citizen interpretation, deterministic corroboration, Google operational forecast, Google Maps and ephemeral officer review. Future concepts: jurisdiction interoperability, durable authorized workflows and notifications. Gemini interpretation alone is not corroboration. No source attribution or custom predictive model is deployed. Phase 2D remains MODEL_NOT_ACCEPTED; no renewed model search is planned in this phase. Stop after Phase 3A.

See [Phase 1C verification](docs/PHASE_1C_VERIFICATION.md), [architecture](docs/ARCHITECTURE.md), [data sources and setup](docs/DATA_SOURCES.md), [Phase 1B verification](docs/PHASE_1B_VERIFICATION.md), and the historical [Phase 1A record](docs/VERIFICATION.md).

Manual provider check, from `apps/api` with the virtual environment activated:

```sh
python scripts/verify_environment_sources.py --lat 28.4595 --lng 77.0266
# Add --json for complete normalized values, timestamps, and provenance.
```

This developer-only command is never run in CI. The **Phase 1B** live verification gate passed on 11 September 2026: all three providers returned HTTP 200 for the fixed NCR probe, followed by verified cache reuse and a controlled partial failure. Run the command with `--gate --json` to repeat the developer-only gate. See the verification report for timestamped results, which are not ongoing monitoring.

## Earth Engine setup (backend only)

Use an Earth Engine enabled and registered Google Cloud project, preferably the existing Google project. Set `EARTH_ENGINE_PROJECT` in root `.env`, or reuse `GOOGLE_CLOUD_PROJECT` as its fallback. The Maps API key does **not** authenticate Earth Engine. Configure local Application Default Credentials (ADC); the application initializes the official Python SDK lazily and keeps startup healthy without credentials.

See [detailed ADC setup and datasets](docs/DATA_SOURCES.md#earth-engine--sentinel-5p). Default query: a 10 km neighborhood, 72-hour lookback ending at the current UTC hour, mean of usable pixels, latest usable scene independently per product. Cache: one hour. Satellite columns retain `mol/m²`; aerosol index is dimensionless. **These are not ground-level concentrations or AQI.**

The full context endpoint includes `satellite` by default. The browser requests ground context with `include_satellite=false`, and `/environment/satellite` independently, so slow satellite queries do not hold up ground cards. Satellite observations and source QA appear in a separate section, with no charts or imagery.

```sh
# From apps/api, after ADC and the project are configured:
python scripts/verify_environment_sources.py --lat 28.4595 --lng 77.0266 --satellite-only --gate --json
```

The full manual gate now covers all sources; exit 1 indicates a ground regression, exit 2 an unmet satellite gate. Genuine empty/filtered satellite searches are valid; configuration and authentication failures are not missing coverage. A wider `--lookback-hours` or explicit `--at` is a separate debug query and must be labelled as such.

Secret checks from the repository root: `python3 scripts/scan_secrets.py --include-build`. The scanner checks Git-visible files and optionally compiled frontend output, with generic token signatures plus exact local provider-key comparisons; it never prints secret values.


## Citizen evidence / Gemini (Phase 2A)

Use **SUBMIT FIELD EVIDENCE** below the environmental probe. Submit one JPEG/PNG, latitude, longitude and optional description. The result separates the original citizen description from a derived interpretation, ordinal confidence, observed features, uncertainty, model and prompt provenance. No incident is created and no environmental query is triggered by submission.

Backend `.env` configuration (never place these in `apps/web`):

```dotenv
GOOGLE_CLOUD_PROJECT=your-existing-project
GOOGLE_CLOUD_LOCATION=global
GEMINI_MODEL=gemini-3.1-flash-lite
GEMINI_TIMEOUT_SECONDS=30
```

Empty location/model values use these defaults; no project returns `not_configured`. Use existing backend Application Default Credentials. Ensure `aiplatform.googleapis.com` is enabled in that project and the principal has Vertex prediction permission (`aiplatform.endpoints.predict`, commonly via `roles/aiplatform.user`), plus service usage access as applicable. No service-account key is needed. The official Google Gen AI Python SDK is pinned in the backend dependency locks. [Google's model documentation](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-1-flash-lite) lists image input, structured output and the global endpoint; model choice remains configurable.

```sh
# Only if API enablement or local ADC setup is needed:
gcloud services enable aiplatform.googleapis.com --project YOUR_PROJECT_ID
gcloud auth application-default login
# Manual live evaluation; never run in CI:
apps/api/.venv/bin/python apps/api/scripts/evaluate_citizen_evidence.py \
  --output docs/verification/phase2a-gemini-live.json
```

For Docker, the existing optional `docker-compose.earth-engine.yml` ADC mount is shared by both Earth Engine and Gemini; `EARTH_ENGINE_ADC_FILE` keeps its established name. Use `-f docker-compose.yml -f docker-compose.earth-engine.yml` and point that variable at the existing host ADC file. No credentials are copied into images. Default Compose health works without ADC, with explicit analysis authentication failures when a project is configured. Restart the backend after changing configuration.

`POST /api/v1/citizen-reports/analyze` accepts multipart fields `image`, `latitude`, `longitude`, `description` (optional, at most 2,000 characters). JPEG/PNG only, at most **5 MiB / 16 MP**, one still frame. Malformed input returns a safe 422; oversize uploads return 413. A valid submission returns HTTP 200 with `status`, original `report`, nullable `analysis` and `evidence`, a safe message, request ID and inference latency. Provider failure never invents an interpretation.

Images are decoded, oriented, stripped of metadata and resized to at most 2048 pixels per edge before inference. AirshedOS retains no images. Phase 2B holds structured report metadata and interpretation in bounded server memory for 30 minutes (up to 256 reports), with earlier capacity eviction or restart loss. Multipart files may spool temporarily above 1 MiB and are closed/deleted within the request; cleaned images stay in memory. The browser preview remains only until clear/replacement/navigation. Google processes the submitted image/context under its service policies; this does not assert zero retention by the cloud provider. Avoid identifying content. No facial/plate recognition, identity inference, database or upload gallery is implemented.

See [Phase 2A verification](docs/PHASE_2A_VERIFICATION.md) for live results, limitations and exact regression checks, and [synthetic fixture provenance](apps/api/scripts/citizen-evaluation/README.md).

## Transparent corroboration (Phase 2B)

After interpretation, click **Corroborate with environmental data**. The backend retrieves its temporary structured report by ID, looks up AQ/weather/FIRMS/Sentinel-5P concurrently using the existing provider caches, and applies the [versioned checklist](docs/CORROBORATION_RULES.md). The Evidence Fusion Card shows a categorical result, each source's contribution or absence, an advisory next step and expandable provenance.

```text
Image → Gemini → structured report (memory, no image)
                         ↓ explicit corroborate
          AQ / Weather / FIRMS / Sentinel-5P
                         ↓ deterministic checklist
            assessment → Evidence Fusion Card
```

`POST /api/v1/citizen-reports/{report_id}/corroborate` takes no body. It does not accept browser-supplied analysis, reupload an image or rerun Gemini. Expired/unavailable IDs return 404; successful analyses expose `structured_report_ttl_seconds` additively. The temporary repository resets with the API and requires the existing single worker. No demo incident, authority task or notification is created.

Image capture time is unknown. Environmental evidence uses **submission_time_proxy**, with current-service semantics for ground providers and an explicit satellite window. All satellite products retain native units and remain context-only. Missing evidence is not a contradiction. STRONG/MODERATE/WEAK/INSUFFICIENT/CONFLICTING are checklist categories, never probabilities, source confirmation or legal findings.

Configuration defaults and exact aggregation are in [CORROBORATION_RULES.md](docs/CORROBORATION_RULES.md). See [Phase 2B verification](docs/PHASE_2B_VERIFICATION.md) for automated checks and the separately labeled synthetic live transport test. Prediction, BigQuery, mapping and persistent operational workflows are future work.
