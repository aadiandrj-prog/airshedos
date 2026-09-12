# AirshedOS

**AI Pollution Incident Command — Phase 1B environmental data foundation.**

Indian cities receive fragmented citizen, air-quality, fire, weather, and satellite signals. AirshedOS is an incident command concept for combining that evidence, communicating uncertainty, and coordinating a response across jurisdictions.

The command center preserves **one fictional Delhi–Gurugram-border incident**, served by FastAPI to a Next.js command center. It includes evidence provenance, an illustrative six-hour risk forecast, acknowledgment, and simulated jurisdiction sharing. **This incident remains a demo.** A separate coordinate probe now retrieves current Google Air Quality, Google Weather, and NASA FIRMS context through backend adapters. Missing keys produce explicit `not_configured` states; no substitute readings are shown. AI inference and real notifications are not implemented.

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
    tests/                # Endpoint, schema, state, and concurrency tests
    scripts/              # OpenAPI export and manual provider verification
    openapi.json          # Generated API contract
    pyproject.toml
    requirements*.lock    # Exact Python dependency versions
    Dockerfile
  web/
    src/app/              # Single command-center page and responsive styles
    src/components/       # Replaceable geographic schematic
    src/lib/              # API client and generated domain types
    e2e/                  # Browser checks against the running API
    package.json
    package-lock.json
    Dockerfile
docs/
  ARCHITECTURE.md
  VERIFICATION.md         # Historical Phase 1A result
  PHASE_1B_VERIFICATION.md
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
python -m pip install -r requirements-dev.lock
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

Open [the command center](http://localhost:3000) and [interactive API docs](http://localhost:8000/docs). The default API URL works without creating an environment file. All UI timestamps are displayed in IST with the date; API timestamps include a timezone.

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

After model changes, regenerate both OpenAPI and TypeScript definitions and commit them together. CI detects stale generated files. Backend and frontend checks run on every push and pull request.

Browser checks require both apps running, ideally after a fresh backend start so the first test exercises both mutations:

```sh
cd apps/web
npx playwright install chromium
npm run test:e2e
```

These checks cover real API connectivity/actions, reload behavior, evidence, desktop/mobile screenshots, connection failure, loading, empty state, and failed actions. Browser regression screenshots are saved under ignored `apps/web/test-results`; curated verification captures are under `docs/screenshots`. Environmental display tests also intercept explicitly synthetic provider fixtures to verify readings, units, cached states, partial responses, and zero detections; these are not live integration evidence. Browser checks are local and are not part of the lightweight CI workflow.

## Data and limitations

- The incident workspace’s environmental values, locations, evidence scores, and forecasts are hand-authored fixtures. The fixed scenario date is 10 September 2026; it does not refresh to masquerade as a live observation.
- Confidence and probabilities use 0–1 in the API and percentages in the UI. The 86% confidence and 81% spike risk are illustrative, not calibrated model outputs.
- Satellite evidence is explicitly unavailable, with no observation time or confidence invented for it.
- State resets when the API restarts, including on development reload. A single process is required; there is no persistence or multi-worker coordination.
- Acknowledgment is stored locally. Sharing records a simulation and sends nothing externally.
- The geographic pane is a schematic, not a navigable map or reliable geographic boundary. Possible transport is illustrative; it is not a dispersion model.
- Environmental providers are independent of incident evidence. They do not alter demo confidence, forecasts, or actions. The probe fetches on page load and on **Check conditions**; there is no background monitoring.
- Provider outages and missing credentials are expected. FIRMS `null` means unavailable; an empty list means a valid query returned zero nearby detections.
- Optional timezone-aware `at` is preserved as reference metadata only. All provider requests remain current, with their own observation times.
- No authentication, production deployment, historical storage, or automatic attribution is included.

## Planned architecture (not implemented)

Citizen/environmental signals → Gemini multimodal → environmental data adapters → BigQuery → Vertex AI prediction → evidence fusion → command center → jurisdiction sharing.

Google Air Quality, Weather, and FIRMS adapters are implemented in Phase 1B. Earth Engine, Gemini, Vertex AI, mapping, persistence, and predictions remain planned only. **Phase 1C has not begun.**

See [architecture](docs/ARCHITECTURE.md), [data sources and setup](docs/DATA_SOURCES.md), [Phase 1B verification](docs/PHASE_1B_VERIFICATION.md), and the historical [Phase 1A record](docs/VERIFICATION.md).

Manual provider check, from `apps/api` with the virtual environment activated:

```sh
python scripts/verify_environment_sources.py --lat 28.4595 --lng 77.0266
# Add --json for complete normalized values, timestamps, and provenance.
```

This developer-only command is never run in CI. The live verification gate passed on 11 September 2026: all three providers returned HTTP 200 for the fixed NCR probe, followed by verified cache reuse and a controlled partial failure. Run the command with `--gate --json` to repeat the developer-only gate. See the verification report for timestamped results, which are not ongoing monitoring.
