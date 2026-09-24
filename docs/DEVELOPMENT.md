# Developer setup

For a plain-language introduction, start with the [README](../README.md). This guide covers local development; [HOSTING.md](HOSTING.md) covers the requested public hosting setup.

## Prerequisites

- Node.js 22 or newer and npm
- Python 3.12 or newer (3.13 recommended)
- Or Docker with Compose for the container setup

The backend uses **one worker** because workflow records and caches are held in process memory. There is no SQL integration. An empty Neon project does not make application records persistent.

## Local development

From the repository root, start the backend:

```sh
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

On Windows, activate with `.venv\Scripts\activate`.

In a second terminal, from the repository root:

```sh
cd apps/web
npm ci
npm run dev
```

Open [the app](http://localhost:3000) and [API documentation](http://localhost:8000/docs). Without provider credentials, the fictional demo works and sources report their configuration state honestly.

For live providers, copy root `.env.example` to root `.env` and populate the needed settings locally. Never commit this file. Start the API with `--env-file ../../.env` in addition to the options above. The web configuration explicitly reads only Maps browser settings from the root file; `NEXT_PUBLIC_API_BASE_URL` can be set in `apps/web/.env.local` or the frontend process environment.

| Configuration | Scope |
| --- | --- |
| `GOOGLE_MAPS_PLATFORM_API_KEY` | Backend only: Google AQ, Weather and forecast |
| `NASA_FIRMS_MAP_KEY` | Backend only: FIRMS |
| `GOOGLE_CLOUD_PROJECT`, `EARTH_ENGINE_PROJECT` | Backend cloud/registered Earth Engine projects |
| `GOOGLE_CLOUD_LOCATION`, `GEMINI_MODEL` | Backend Gemini configuration |
| `CORS_ORIGINS` | Exact frontend origins allowed by the backend |
| `NEXT_PUBLIC_API_BASE_URL` | Public backend URL, compiled into the frontend build |
| `NEXT_PUBLIC_GOOGLE_MAPS_BROWSER_KEY` | Separate browser-restricted Maps JavaScript API key |
| `NEXT_PUBLIC_GOOGLE_MAPS_MAP_ID` | Optional map ID |

Gemini and Earth Engine also require backend Google Application Default Credentials (ADC); the Maps key does not authenticate them. Use `gcloud auth application-default login` for local development. See [provider setup](DATA_SOURCES.md) and [citizen evidence verification](PHASE_2A_VERIFICATION.md). Do not upload a personal ADC token cache to a hosting service.

`OPENAQ_API_KEY` and the dataset/model dependency locks are for separate offline research. They are not needed to run the app. The [dataset](PREDICTION_DATASET.md) and [model](PREDICTION_MODEL.md) records preserve the rejected research result.

## Docker

From the repository root:

```sh
docker compose up --build -d --wait
docker compose ps
# When finished:
docker compose down
```

The frontend is at localhost:3000 and API at localhost:8000. Compose optionally reads root `.env`; ports bind to loopback. The browser uses the reachable API URL, not the Docker service name.

For existing local Google ADC:

```sh
EARTH_ENGINE_ADC_FILE="$HOME/.config/gcloud/application_default_credentials.json" \
  docker compose -f docker-compose.yml -f docker-compose.earth-engine.yml up --build -d --wait
```

This read-only credential mount is shared by Gemini and Earth Engine. Credentials are not copied into images. Restarting the backend clears temporary records and caches.

## Checks

From `apps/api`, with the virtual environment active:

```sh
ruff check .
ruff format --check .
pytest -q
python scripts/export_openapi.py
```

For the full offline research tests, install the additional locked development dependencies used in [CI](../.github/workflows/ci.yml), including `requirements-model.lock`.

From `apps/web`:

```sh
npm ci
npm run generate:api
npm run lint
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
```

Browser checks require both services running; use the production Docker build for the full suite. Maps/provider responses are mocked in CI, which never calls live Google APIs. Generated OpenAPI, frontend types and the PollutionEvent JSON Schema must stay consistent.

From the repository root:

```sh
python3 scripts/scan_secrets.py --include-build
```

Manual live checks use the existing scripts in `apps/api/scripts` and `apps/web/scripts`. Follow [DEMO_CHECKLIST.md](DEMO_CHECKLIST.md) for preflight and the real synthetic-input rehearsal. These calls use actual provider quota; historical verification is not continuous monitoring.

## Code and contracts

- `apps/web`: Next.js command center, UI components, generated API types, browser tests.
- `apps/api/app`: FastAPI endpoints, providers, evidence rules, review and handoff repositories.
- `apps/api/prediction`: offline research; not imported by the runtime app.
- `/docs` and `/openapi.json` on the API: complete current endpoint documentation.
- `/health`: process responds. `/ready`: fictional repository initialized; external providers are not required.

For domain details, see [architecture](ARCHITECTURE.md), [corroboration](CORROBORATION_RULES.md), [forecasting](FORECASTING.md), and [interoperability](INTEROPERABILITY.md). Preserve historical verification records and `MODEL_NOT_ACCEPTED` when making new changes.
