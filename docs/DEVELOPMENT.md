# Developer setup

For a plain-language introduction, start with the [README](../README.md). This guide covers local development; [HOSTING.md](archive/prototype/HOSTING.md) covers the requested public hosting setup.

## Prerequisites

- Node.js 22 or newer and npm
- Python 3.12 or newer (3.13 recommended)
- Or Docker with Compose for the container setup

The default demo backend uses **one worker** because its workflow records and caches
are held in process memory. Phase 1 adds an internally injected PostgreSQL foundation,
with no new public routes or implicit production database connection. See the
[persistence guide](seva/PHASE_1_PERSISTENCE.md) for isolated PostgreSQL 18 setup,
required integration tests and local private-media cleanup. An empty Neon project
alone does not make the deployed demo persistent.

Phase 2 adds managed identity and scoped v2 APIs plus `/resident` and `/authority`
shells. Follow the [access guide](seva/PHASE_2_ACCESS.md) for Auth0/server configuration,
separate database grants, controlled operator provisioning and signed local integration
tests. `APP_MODE=pilot` must be explicit on both services; it blocks legacy v1 routes.
The default remains the existing prototype. Next.js server identity settings belong
in its own ignored `.env.local`, not in public environment fields or a copied root
provider-secret file. Live identity/hosted setup remains separately pending.

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

Gemini and Earth Engine also require backend Google Application Default Credentials (ADC); the Maps key does not authenticate them. Use `gcloud auth application-default login` for local development. See [provider setup](DATA_SOURCES.md) and [citizen evidence verification](archive/prototype/PHASE_2A_VERIFICATION.md). Do not upload a personal ADC token cache to a hosting service.

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

Manual live checks use the existing scripts in `apps/api/scripts` and `apps/web/scripts`. Follow [DEMO_CHECKLIST.md](archive/prototype/DEMO_CHECKLIST.md) for preflight and the real synthetic-input rehearsal. These calls use actual provider quota; historical verification is not continuous monitoring.

## Code and contracts

- `apps/web`: Next.js command center, UI components, generated API types, browser tests.
- `apps/api/app`: FastAPI endpoints, providers, evidence rules, review and handoff repositories.
- `apps/api/prediction`: offline research; not imported by the runtime app.
- `/docs` and `/openapi.json` on the API: complete current endpoint documentation.
- `/health`: process responds. `/ready`: fictional repository initialized; external providers are not required.

For domain details, see [architecture](ARCHITECTURE.md), [corroboration](CORROBORATION_RULES.md), [forecasting](FORECASTING.md), and [interoperability](INTEROPERABILITY.md). Preserve historical verification records and `MODEL_NOT_ACCEPTED` when making new changes.

## Resident pilot development

The resident routes use the Phase 2 managed identity/BFF and PostgreSQL domain,
not the default prototype's in-memory reports. See [access setup](seva/PHASE_2_ACCESS.md)
and [resident implementation](seva/PHASE_3_RESIDENT.md). Both services require explicit
`APP_MODE=pilot`; provider credentials are unnecessary for text acceptance. A
separately operator-approved `PILOT_TRIAGE_UNIT_ID` is required for new intake.
Use the separate migration credentials to apply `seva_0004`; application startup
does not migrate anything. Never aim the synthetic test commands at a hosted DB.

After starting the disposable PostgreSQL service in `docker-compose.persistence.yml`:

```sh
# apps/api; explicit disposable database only
export TEST_DATABASE_URL='postgresql+psycopg://seva_test:synthetic_local_only@127.0.0.1:55432/seva_phase1_test'
SEVA_MIGRATION_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/alembic upgrade head
TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest -q
# Then apps/web, retaining TEST_DATABASE_URL in this terminal
npm run test:identity
npm run test:resident
```

Run database tests and the browser harness sequentially: backend test fixtures reset
the named disposable schema. The resident harness starts an ephemeral HTTPS OIDC
fixture, local API and Next.js server, then drives the actual SDK login and private
BFF at 390×844. It generates temporary certificates and synthetic principals;
its provider/transport/management helpers live under tests, outside the app image.
No environment switch enables a production test login. It uses no live provider
keys, does not send messages, and removes its temporary services/private files.
CI runs these checks against its own disposable PostgreSQL service.

Private uploads require an approved **private** Cloudflare R2 bucket and the
server-only variables documented in root `.env.example`. No local disk fallback
is configured in production. Without approved storage, submit text only. Sources
are bounded to 4,000,000 bytes and 16 MP; only stripped/resized JPEG derivatives
are written, under `seva-private/derivatives/`. Objects are read through authorized
API paths, never a public URL or browser presigned link. Confirm bucket privacy,
prefix-scoped credentials and deletion before enabling real collection.

Schedule `python -m app.resident.maintenance` at least every minute in the hosted
environment with separate `SEVA_CLEANUP_DATABASE_URL` and approved storage
credentials. This command performs retention cleanup/reconciliation, not analysis
processing. Access expiry is immediate in the API; physical deletion and backup
retention require the separately verified scheduler and operational policy. No
scheduler, bucket, live identity tenant or hosted migration was provisioned here.

## Authority pilot development

Phase 4 adds the unit-scoped review routes, explicit public-message previews,
field follow-up, scoped metadata export and membership administration. See
[the authority report](seva/PHASE_4_AUTHORITY.md). Apply `seva_0004` with separate
migration credentials; no production migration is run by app startup.

After the backend fixtures, run these against the same guarded disposable database:

```sh
# apps/web, with TEST_DATABASE_URL already set to the named local test target
npm run test:identity
npm run test:resident
npm run test:authority
```

The authority harness extends the local HTTPS provider fixture with exact synthetic
reviewer/admin subjects and pre-approved test memberships. It exercises real signed
sessions and SQL permission queries, not page-redirect mocks or a production login
bypass. Its failing Gemini adapter is factory injected and makes no cloud call.
Do not run database-resetting pytest concurrently with either browser harness.

Phase 5 replaces synchronous enrichment with durable jobs and a separate worker.
Historical `MANUAL_ENRICHMENT` metadata remains historical; refresh HTTP calls return 202. It uses the original report inputs; resident supplements
are separate human-review material. Default retained-provider collection is off.
Only after policy/purpose/backup approval, verified cleanup and hosted rehearsal may
an operator configure `RETAINED_PROVIDER_CONTENT_APPROVED=1`. Successful cleanup
health must remain within 120 seconds and have no overdue protected-data backlog;
run `python -m app.resident.maintenance` at least every minute with separate cleanup
credentials. Source-operation budget units are pilot admission limits, not measured
provider capacity or exact billing counters. No task here provisions a scheduler.

Optional resident/reviewer Google context uses CSRF-protected POSTs and volatile
15-minute retention. Saved evidence and manual export never contain those values or
derived hashes. Export v2 is recent metadata with explicit totals/truncation and a
canonical packet hash; legacy packet/schema behavior remains preserved.

A populated downgrade to v3 is intentionally refused when manual/source kinds cannot
be represented. Preserve a reviewed backup and follow a separately approved rollback
plan rather than forcing conversions. Test fixtures clear only their explicitly
named disposable records before exercising structural rollback/reapply.


## Phase 5 worker (explicit pilot only)

Use the API Python environment. Migrate a disposable local test database with the
existing Alembic tools; production migration is a separately authorised operation.
Review `apps/api/scripts/worker_roles.sql` for a dedicated worker login; it deliberately
has no session-token table access. Do not reuse BFF/session credentials.

```sh
# Set APP_MODE=pilot and SEVA_WORKER_DATABASE_URL in the private process environment.
# Configure approved private storage and source settings only after policy review.
cd apps/api
.venv/bin/python -m app.processing --metrics
.venv/bin/python -m app.processing --once
.venv/bin/python -m app.processing
```

A normal worker polls every two seconds, uses database-clock leases (default 120s),
heartbeats at 30s, and stops after three deliveries per logical run. Retry waits are
30/120s. `SEVA_WORKER_LEASE_SECONDS` explicitly accepts 1–600 seconds; short leases are
for controlled recovery tests, not an empirically measured production recommendation.
No provider or object-store IO holds a database row lock. Whole failed attempts can
repeat successful external calls after crashes; no exactly-once billing guarantee.
A usable partial source snapshot is frozen once; an explicit refresh gets a new version.

Opt-in `docker-compose.worker.yml` needs `SEVA_WORKER_ENV_FILE` naming a private env
file; it provisions no cloud resources. The Render review example is under docs/seva
and is not activated by root render.yaml. The existing free web service alone does
not establish a running worker. A separate continuous host and hosted kill/recovery
rehearsal remain release gates. Keep cleanup scheduled at least each minute; missing
or stale health terminates configured-source work safely, while acceptance remains
available. Requeue through an authorised reviewer refresh after fixing the cause.
No retries resurrect suppressed/expired content. A restore must remain disconnected
from workers until deletion-ledger reconciliation, lease invalidation and full cleanup
have passed; the live backup/restore design is still an external release gate.

Run `TEST_DATABASE_URL=... .venv/bin/python -m pytest -q` for full deterministic gates.
`tests/test_processing.py` includes actual subprocess SIGKILL/restart, PostgreSQL
concurrency, fencing, quotas, source failures, permissions and retention. Synthetic
browser fixture `process-jobs` is local-only tooling, excluded from the production image.
Do not run database-resetting pytest concurrently with browser/identity harnesses.


## Phase 6 verification and private release

See [the runbook](seva/PILOT_RUNBOOK.md), [validation report](seva/PHASE_6_VALIDATION.md)
and [blank private environment template](seva/pilot.env.example). Apply `seva_0006`
on a disposable local database before starting current runtime. Fresh databases are
quarantined; API/worker need a released `SEVA_RECOVERY_EPOCH` held outside backups.
Only the offline approved management login can initialise a genuinely empty database
or quarantine/reconcile/release an existing one. Do not reuse a restored database UUID.
Runtime never migrates or bootstraps automatically. An approved triage unit/current
reviewer, worker heartbeat and cleanup are required by pilot readiness. Optional source
configuration is explicitly not live verification. Prototype mode now rejects private
pilot and live-provider configuration, so do not load an old live-provider .env into a
synthetic demo process. These local changes have not altered the deployed site.

For all backend checks supply the explicitly named local database **and**
`SEVA_TEST_PG_CONTAINER` identifying its disposable PostgreSQL 18 Docker container.
The actual backup/restore test creates/drops only `seva_restore_test`, distinct from
`seva_phase1_test`, and tests actual database restart. It uses PG18 tools inside that
container (a host PG14 client is not sufficient). Keep no other test/browser process
using the same disposable database while pytest resets it. `SEVA_EVIDENCE_DIR` may name
an explicit output directory for minimised synthetic timing observations.

After backend checks:

```sh
# apps/web, TEST_DATABASE_URL set to the guarded disposable target
npm run test:identity
npm run test:resident
npm run test:authority
npm run test:pilot
```

`test:pilot` builds with Maps/telemetry disabled, copies standalone assets and runs the
resident/reviewer suites over local HTTPS using production secure cookies and strict
server-side TLS. Its synthetic signed OIDC transport is test-only. A separate API and
worker run; that fixture worker also performs local cleanup. Test queue delays/retry
waits are deliberately controlled, not production timing measurements. Browser contexts
refuse nonlocal network traffic. Generated certificate/key/private files are temporary;
no fake login route ships in the application image. Phase 7 now styles the pilot UI with
scoped light tokens; the isolated prototype presentation is preserved.
Pilot map approval is a **build-time** `NEXT_PUBLIC_PILOT_MAPS_APPROVED=1` choice and needs
separate privacy/purpose review; a key alone does not enable it.

Use the separately installed audit tool to check the locked runtime dependencies,
`pip-audit --no-deps --disable-pip -r requirements.lock --format json`, and use
`npm audit --omit=dev` for production frontend dependencies. These are time-dependent
advisory checks, not scientific tests or zero-vulnerability proof. The full development
audit retains the documented moderate minimatch/TypeScript ESLint chain; do not apply
an unsupported major override silently. The versioned exploratory case split/protocol
under docs/seva/evaluation/v1 contains synthetic scenarios only and no participant rows.

Resident context request shape is now `{ "report_id": "UUID" }`, with saved coordinates
and current owner/approved-unit checks before quota admission and again after provider IO.
The pre-submit component does not call sources; saved detail reuses the component.
Old coordinate-only bodies are rejected. This is a permission correction, not a new
public environmental proxy. Regenerate OpenAPI/TS after this v2 pilot request change.


## Phase 7 UI verification

The pilot home, account shells, resident flow and review workspace use the shared
`src/app/pilot.css` tokens and locally served Geist. `APP_MODE=pilot` is still required
for the editorial public home; prototype mode keeps its isolated legacy command centre.
See [the chosen direction](seva/DESIGN_DIRECTION.md) and [Phase 7 report](seva/PHASE_7_POLISH.md).

Run the same signed-identity and browser harnesses serially against the guarded local
PostgreSQL database. `npm run test:pilot` includes seven resident/accessibility-state tests
and two full reviewer/admin tests, captures 390px/1440px synthetic screenshots and runs
axe-core 4.13.0 WCAG A/AA-tag checks. It blocks nonlocal browser traffic and makes no
paid-provider requests. `SEVA_CAPTURE_STAGE=before` selects the before output folder;
normal runs write after captures. Do not run the before mode after design changes and
call its output a historical baseline. The recorded Phase 7 baseline was captured before
any visual implementation. No synthetic principal route is added to the product.

Capture checks assert no overflow, form keyboard/focus behavior, 320px/200% text reflow,
reduced motion and computed contrast. They are bounded Chromium checks, not a full
accessibility certification. Repeat `npm run lint`, `npm run typecheck`, `npm run build`,
legacy `npm run test:e2e`, generated-contract/protected-record checks and the root secret
scan. The complete API suite remains relevant for the unchanged privacy/workflow contract.

Re-running the harness replaces after screenshots and accessibility records with fresh
synthetic IDs/times. Refresh the capture/source manifest for a new handoff; it is not a
pixel-golden CI assertion or a snapshot of secret/deployment configuration.
