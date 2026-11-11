# Phase 0 — baseline and implementation blueprint

Executed 10 November 2026, Asia/Kolkata. This is a fresh local verification,
separate from the October audit and September milestone records.

## Checkout and permitted change

- Selected working checkout:
  `<authorised AirshedOS checkout>`.
- Source revision: `6f071afd10f0ffed024448ac87d3bfae9ec8abc4`, dated 26 September.
- Entry branch: `codex/hosting-provider-verification`; tracked tree clean.
- Phase branch: `codex/seva-phase-0`, created locally at that same revision.
- Origin: `https://github.com/aadiandrj-prog/airshedos.git`.
- Fresh read-only GitHub main check: `142dfc1542621e18e99e1a1a452e4756e5fd615b`.
  `git merge-base --is-ancestor <remote-main> HEAD` passed. Local HEAD adds the
  provider-recovery documentation commit; it is not an older source checkout.
- No AGENTS.md was found in the selected root's ancestor paths or application,
  docs and CI subtrees. No existing `docs/seva` files were present.
- Unrelated untracked `.airshed-*`, `.chart-data-*`, `AirshedOS Deck/`, speaker
  notes and `output/` material were preserved. No other clone was edited/copied.
- Phase output is only the four requested Markdown files in `docs/seva/`.
  No runtime recovery was necessary. No migration, package installation,
  provisioning, commit, push or deployment was performed.

The actual source revision remains the hash above; Phase 0 documentation is an
uncommitted worktree change on the local phase branch. A later commit may record
these documents; it must not imply any new runtime feature is deployed.

## Inspected implementation

Read current [architecture](../ARCHITECTURE.md), [data sources](../DATA_SOURCES.md),
[development](../DEVELOPMENT.md), [hosting](../archive/prototype/HOSTING.md), the API models/routers,
repositories, provider service/forecast boundary, browser API client, CI, hosting
configuration and generated contracts. Principal implementation facts:

- The frontend has one command-center page at `/`, rather than resident and
  authenticated reviewer route spaces. It calls FastAPI directly from the browser.
- The API has 20 operations and no application identity/ownership/unit security.
  CORS restricts browser origins; it does not authorize users or direct clients.
- Image analyze requires a JPEG/PNG. It preprocesses metadata-free bytes and calls
  Gemini synchronously; only successful interpretation enters the temporary
  structured-report repository. A text-only durable acceptance route does not
  exist. A failed analysis does not produce a reviewable persistent report.
- Corroboration accepts a server report ID, retrieves context and then separate
  forecast, and inserts an in-memory case. The case ID is assessment-derived.
- Storage is process-local: 256 structured reports / default 30 minutes, 64
  officer cases bounded by originating report expiry, 128 handoffs / one hour.
  Restart/eviction removes them. There is no application PostgreSQL integration,
  durable queue, persistent private media, resident ownership or operator membership.
- Review changes only workflow metadata and uses revisions. Handoffs preserve
  frozen payloads, SHA-256 and append-only temporary audit, but all recipients
  are simulated. `pollution_event_v1` requires Gemini-shaped evidence.
- Gemini and support are advisory. Satellite columns remain regional context.
  Forecast is attached after rule evaluation; 6/12/24-hour values are window peaks.
- `MODEL_NOT_ACCEPTED` and the isolated offline research remain unchanged. Current
  pytest includes synthetic model-regression fixtures; no real historical model
  training, selection, dataset rebuild or locked-test evaluation ran here.
- `render.yaml` targets a free Docker web service with one Uvicorn worker;
  Vercel runs the Next.js frontend. The Neon project is historically documented
  as empty/disconnected; its current schema was not verified in this phase.
- Earlier SYSTEM_OVERVIEW/phase deployment statements are stale relative to
  HOSTING.md. The user reports the public app is live. No new live URL, service
  availability or deployed revision is asserted from this local verification.

### Existing route exposure

All paths below are current v1 behavior, **unauthenticated at this baseline**.
OpenAPI inventory and actual router/dependency inspection agree. Phase 0 does
not change exposure; pilot cutover must close alternate paths before real intake.

| Method | Path | Current behavior |
|---|---|---|
| GET | `/health` | Process health |
| GET | `/ready` | Fictional repository initialized; not provider/DB/worker health |
| GET | `/api/v1/incidents` | Shared fictional fixture list |
| GET | `/api/v1/incidents/{incident_id}` | Fictional detail |
| POST | `/api/v1/incidents/{incident_id}/acknowledge` | In-memory demo mutation |
| POST | `/api/v1/incidents/{incident_id}/share` | Simulated demo sharing |
| GET | `/api/v1/environment/sources` | Backend configuration presence |
| GET | `/api/v1/environment/context` | Arbitrary validated coordinate; quota-bearing sources if configured |
| GET | `/api/v1/environment/satellite` | Coordinate satellite query |
| GET | `/api/v1/environment/forecast` | Coordinate Google forecast |
| POST | `/api/v1/citizen-reports/analyze` | Image/provider processing; no authenticated owner |
| POST | `/api/v1/citizen-reports/{report_id}/corroborate` | Temporary report assessment and case insertion |
| GET | `/api/v1/review/cases` | Shared temporary case queue |
| GET | `/api/v1/review/cases/{case_id}` | Full temporary case snapshot |
| POST | `/api/v1/review/cases/{case_id}/review` | Revision-based manual review |
| POST | `/api/v1/review/cases/{case_id}/handoffs` | Frozen simulated packet creation |
| GET | `/api/v1/handoffs` | Shared source/destination summary filters |
| GET | `/api/v1/handoffs/{handoff_id}` | Packet and temporary audit |
| POST | `/api/v1/handoffs/{handoff_id}/transition` | Simulated state transition |
| GET | `/api/v1/handoffs/{handoff_id}/export` | Exact canonical v1 JSON |

FastAPI's default `/docs`, `/redoc` and `/openapi.json` also exist; they are
framework documentation routes, not additional domain operations. The legacy
fixture has illustrative 86% incident confidence and 81% forecast probability;
these are hand-authored demo values and cannot be migrated as scientific scores.
Five synthetic citizen-evaluation images and browser/provider fixtures are tests,
not resident reports. No fixture was used to claim fresh live-provider success.

## Actual available environment

| Component | Observed version |
|---|---|
| Node / npm | 24.14.1 / 11.11.0 |
| API Python | 3.13.5 (`apps/api/.venv/bin/python`) |
| FastAPI / Pydantic / Uvicorn | 0.141.1 / 2.13.5 / 0.52.4 |
| HTTPX / google-genai / earthengine-api | 0.28.1 / 2.23.0 / 1.7.43 |
| pytest / Ruff | 9.1.1 / 0.16.6 |
| Next.js / React / TypeScript | 16.3.4 / 19.3.0 / 5.9.3 |
| Playwright | 1.63.0 |
| Docker daemon / Compose | 29.9.1 / 5.6.0 |

Auth0 Next.js SDK, SQLAlchemy, Alembic, psycopg, PyJWT and boto3 are not installed
in the inspected application environments. Local `.env` presence-only checks
found no values for new Auth0, database/migration or S3/R2 settings. This does
not prove external services/accounts do not exist. No secret values were emitted.

## Fresh verification results

Commands use repository root unless a working directory is specified.

| Check / command | Actual result |
|---|---|
| API cwd: `.venv/bin/python -m pytest -q` | **536 passed**, 3 non-failing warnings, **32.93 s** |
| `apps/api/.venv/bin/ruff check apps/api` | PASS |
| `apps/api/.venv/bin/ruff format --check apps/api` | PASS; 92 Python files already formatted |
| Web cwd: `npm run lint` | PASS |
| Web cwd: `npm run typecheck` | PASS; Next route generation and TypeScript |
| Web cwd: `npm run build` | PASS; optimized Next.js production build |
| Web cwd: `npm run test:e2e` | **58 passed**, approximately **1.1 minutes**, production standalone server |
| OpenAPI and receiver schema regeneration comparison | PASS; repository exporter regenerated byte-identical files |
| Frontend generated API type comparison | PASS; `npm --prefix apps/web run generate:api`, no diff |
| Build-inclusive secret scan | PASS; 2,171 files, zero findings |
| Phase document links/contract checks and tracked diff | PASS; four documents, all 20 legacy operations mapped, six fingerprints unchanged, no tracked source diff |

The backend warnings concern Starlette/httpx compatibility, AnyIO's deprecated
BlockingPortal alias and platform CPU-count detection. Browser output has the
existing NO_COLOR/FORCE_COLOR environment warning. No assertions were removed.

Browser baseline used temporary native local processes, not a new deployment:

```sh
# apps/api; do not load the provider-bearing root .env
env GOOGLE_MAPS_PLATFORM_API_KEY= NASA_FIRMS_MAP_KEY= \
  GOOGLE_CLOUD_PROJECT= EARTH_ENGINE_PROJECT= \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# apps/web; production bundle produced by npm run build
cp -R .next/static .next/standalone/.next/static
cp -R public .next/standalone/public
env HOSTNAME=127.0.0.1 PORT=3000 node .next/standalone/server.js
npm run test:e2e
```

Provider values are disabled in the local API, Maps/forecast/provider test routes
are mocked, and backend tests block real transports. Static asset copies are
ignored build output only. Browser tests modify only the disposable local demo
process and ignored test artifacts. The temporary servers are stopped at handoff.
Docker availability was checked read-only; no Docker image build, compose
restart, cloud call with provider credentials or production-record operation ran.

## Preserved contract and scientific-record fingerprints

These SHA-256 values were measured before writing Phase 0 documents and checked
again at completion. They identify current baseline files, not a new model run.

| File | SHA-256 |
|---|---|
| `apps/api/openapi.json` | `e9ce14cb7ad8cadc6a1f2b4e8a0ee33c3b646366210a620775c3764066ad0163` |
| `apps/web/src/lib/api-schema.d.ts` | `ab8e4a8544f380ad727fb3fcec2c96b2675f909006b7a32437bfcabfdc9d8337` |
| `docs/contracts/pollution_event_v1.schema.json` | `a79b1c054c931039f06744d445064fa6a0ef1f34023c25f1dff7b0dd02b2b3ca` |
| `docs/evidence/phase2d_decision.json` | `8ade7949255892f3f2706299be6dfad1c10216dd608374111acd9ccb8e0074bc` |
| `configs/prediction_model_v1.json` | `3518d7fb45ec39afc77abaf24eef20c42cfee2a967ec885d0051fb0f759046c2` |
| `docs/contracts/protected-records.json` | `4528fc3e5e1bbe8ba70c1c67317b4957df771b79d43a98fd1262c5ab30ace93d` |

## Outputs, decisions and boundaries

Delivered [IMPLEMENTATION_BLUEPRINT.md](IMPLEMENTATION_BLUEPRINT.md),
[DECISIONS.md](DECISIONS.md), [PHASE_STATUS.md](PHASE_STATUS.md) and this report.
They freeze routes, approved unit access, safe response projections, report/case/
processing/evidence/review/publication separation, workflow mapping, transaction/
idempotency and worker semantics, media/privacy handling, retention/redaction,
new export version boundaries, configuration and later-phase acceptance gates.

Routine choices: Auth0 OIDC with database-backed Next sessions/BFF; independently
validated RFC 9068 API tokens and current DB memberships; PostgreSQL 18 with
SQLAlchemy/Alembic/psycopg; private R2/S3 media with local adapters; Postgres-backed
jobs and a separate Render worker only after authorization. Source retention and
backup restrictions make initial Google context volatile-only. Pilot source
uploads use 4,000,000 bytes to fit the BFF host boundary. These are documented
adaptations, not implemented runtime changes or altered research acceptance gates.

External managed-auth, DB/storage credentials and schema access, worker capacity,
real-provider checks and owner-approved real-data collection policy remain pending.
They do not prevent this locally verified Phase 0 or later local development.
No detailed later-phase prompts were supplied; the blueprint's Phase 1–7 map is
an explicit inferred dependency sequence, to reconcile when those prompts arrive.

Next dependency: separately begin **Phase 1 persistence foundation** using this
contract and disposable local Postgres. Do not run a production migration merely
because Neon is listed in an older hosting document. Phase 0 stops here.

### Final verification

**Phase 0 is locally verified.** All required local gates passed. New application
behavior is not claimed: the four contract/baseline documents are the deliverable.

- Executed the existing repository contract tools:
  `apps/api/.venv/bin/python apps/api/scripts/export_openapi.py`, then
  `npm --prefix apps/web run generate:api`. Comparing OpenAPI, generated frontend
  types and receiver schema with Git returned no diff.
- Ran `python3 scripts/scan_secrets.py --include-build`: PASS, 2,171 files,
  zero findings. No secret values were printed.
- Validated all four documents' local links/whitespace, matched the baseline
  inventory to every one of the 20 OpenAPI domain operations, and checked all
  six fingerprints above. No tracked baseline file changed.
- Reviewed contract consistency across resident/reviewer authorization,
  idempotency, separate processing/review/publication, retention/backup behavior,
  actual host constraints and explicit future-phase gates. Document checks do
  not stand in for future runtime/security integration tests.
- `git diff --check` passed. Temporary local API and standalone web servers were
  stopped. Original untracked presentation/output material remains present.

| Phase 0 acceptance item | Evidence |
|---|---|
| One working checkout and traceable baseline | Exact path/revision, clean tracked entry, remote ancestry and preserved artifacts above |
| Current API/UI/source and fresh checks | Exposure inventory, versions and successful backend/browser/build runs above |
| Concrete product/access/data contract | Blueprint sections 1–6; explicit DTOs, role matrix and state mapping |
| Managed auth/session and DB/media choices | Blueprint sections 4/7/8; ADR-003–ADR-010 |
| Durable acceptance, retries, evidence and host-supported worker | Blueprint section 7 and ADR-007/ADR-008 |
| Retention/private media/deletion/restore and external owner decisions | Blueprint sections 8/10 and ADR-011/ADR-012 / EXT-01–EXT-07 |
| Later-phase checks and stopping boundary | Blueprint section 11; PHASE_STATUS has Phase 1–7 NOT_STARTED |

External/live checks remain explicitly pending. No required Phase 0 local gate
failed, and no Phase 1 database implementation began.
