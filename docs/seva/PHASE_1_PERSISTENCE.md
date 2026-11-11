# Phase 1 — durable case foundation

Date: 10 November 2026 (Asia/Kolkata). Contract: `seva_pilot_v1`.
Status: **COMPLETE_LOCALLY_VERIFIED**. Hosted/live checks remain pending.
Source base: `6f071afd10f0ffed024448ac87d3bfae9ec8abc4`.
Local branch: `codex/seva-phase-1`; implementation is uncommitted worktree changes.
The selected checkout and unrelated presentation/output artifacts were preserved.
No remote push, deployment, production migration, paid provisioning or live-provider
request is part of this phase. The existing public prototype is separate.

## Implemented boundary

The FastAPI factory accepts an optional `DurableRepository` through internal
dependency injection and exposes it only as `app.state.persistence`. The default
application does not read a database URL, connect to PostgreSQL, migrate a schema,
import fictional incidents, or register any new HTTP routes. Existing v1/demo
repositories and readiness behavior remain in memory. An injected repository also
does not register v2 routes, media serving, or a principal-selection endpoint.

An internal `Principal(issuer, subject)` is a trust seam for the future verified
identity adapter, **not an authentication implementation**. Each action looks up
the active local identity. Resident reads require ownership; authority reads and
mutations require approved active membership in the assigned approved non-prototype
unit. Out-of-scope IDs have the same `NotFound` result. Shared grant/identity locks
fence revocation during writes. These local repository checks do not replace Phase 2
token/session/CSRF verification. No test principal is a selectable production mode.

## Schema and transactions

`apps/api/app/persistence/models.py` defines 18 PostgreSQL tables:

| Area | Tables |
|---|---|
| Identity/unit references | users, units, unit_memberships, auth_sessions |
| Intake and custody | reports, cases, media |
| Processing/evidence | processing_attempts, evidence_versions, evidence_fragments, evidence_redactions |
| Review and publication | review_events, internal_notes, reporter_updates, verification_tasks |
| Scheduling/retries/privacy | jobs, idempotency_keys, privacy_requests |

`auth_sessions` contains only a future sealed-token/metadata storage seam; this phase
creates no real sessions or encryption implementation. `verification_tasks` is the
Phase 1 name for the blueprint's pilot field-follow-up records. Creation has an
internal revision/audit seam; assignment/completion/publication workflows remain later work.

`seva_0001` is a frozen Alembic migration, with explicit DDL rather than importing
live model metadata into the revision. It includes foreign keys, one-case-per-report
uniqueness, principal/operation/key uniqueness, one version per retrieval request,
monotonic per-case version uniqueness, allowed states, content bounds, Google-content
rejection and database triggers for frozen evidence and append-only review history.
The case/latest-evidence cycle is created explicitly after both tables exist and
removed before downgrade. No runtime `create_all` is used.

Added stable locked dependencies: SQLAlchemy 2.1.8, Alembic 1.20.1 and
psycopg/psycopg-binary 3.3.8, plus Mako 1.4.3 and MarkupSafe 3.0.4. A comparison
with HEAD confirmed zero version changes to existing dependencies. Consulted the
official [SQLAlchemy 2.1 introduction](https://docs.sqlalchemy.org/en/21/intro.html),
[Alembic migration tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
and [psycopg installation guide](https://www.psycopg.org/psycopg3/docs/basic/install.html).
The psycopg guide labels a development documentation build; the installed package
is the stable 3.3.8 release, not that development build.

Acceptance commits the report, stable UUID case, initial `RECEIVED` update, four stage
records, idempotency record and `PROCESS_REPORT` job in one transaction. It performs
no AI/environment request. A successful result leaves the transaction only after
commit; a rollback produces no receipt or partial case. Text-only intake is valid;
VISUAL is `NOT_APPLICABLE / NO_IMAGE`, capture time stays `unknown`, and no visual
interpretation or absence-of-pollution finding is fabricated. FORECAST is marked
`NOT_APPLICABLE / NOT_RETAINED_BY_POLICY` in this durable pipeline.

Only the server-injected triage unit can receive initial cases. It must be approved
and non-prototype. Without configuration, intake still commits an unassigned case.
Prototype geographic rectangles do not grant access or routing authority. Such cases
remain unavailable to ordinary reviewer repositories. Later authenticated operator
routing must expose only IDs, intake times and routing state until assignment; the
operator command and staffed roster are not built or claimed in this phase.

Idempotency uses a PostgreSQL transaction advisory lock plus SQL uniqueness for
`(principal_id, CREATE_REPORT, UUID key)`. The fingerprint covers normalized declared
fields, owned media ID and a stable aware key-creation timestamp. Identical replay
returns the same report/case/receipt IDs with `replayed=True`; changed content or
creation envelope raises `Conflict`. A future HTTP adapter must map initial/replay
to 201/200 and the replay header; no such API is exposed now. An unseen key older
than 24 hours raises `Gone`; future skew over 60 seconds is rejected. Accepted keys
replay throughout unexpired report retention, without applying the new-key age limit.

Review, note creation, verification requests and refresh requests take explicit
report-then-case locks, recheck membership and compare the expected revision inside
the transaction. The corresponding append-only review event commits atomically.
Evidence arrival advances the revision too, preventing a stale reviewer action from
silently referring to newly arrived evidence. Events bind the version seen at action.
Reviewer operations do not alter frozen evidence bytes. A new retrieval request
has a distinct job and appends a new evidence version; it never replaces history.

`jobs` contains identifiers, safe kind/state and timestamps, not report descriptions,
coordinates or provider JSON. It is a transactional outbox seam only. There is no
claim loop, lease, retries, provider execution or job completion worker. Internal
evidence append tests do not claim that pending analysis jobs have run.

## Private media and failure recovery

The `PrivateMediaStore` protocol provides put-derivative/read/delete/exists/inventory.
`LocalPrivateMediaStore` is explicitly local synthetic storage, outside public/static
directories; it is not a Render disk fallback. Dedicated roots must be owned/private
(0700), files are 0600, keys are random UUID hex, and directory-relative operations
reject traversal and symlink reads. The adapter returns bytes, never public URLs,
original filenames or filesystem paths to a resident projection.

The service checks the pilot 4,000,000-byte source and derivative ceilings and reuses
the existing MIME/content matching, JPEG/PNG still-image, 16 MP, orientation, 2048 px
resize and metadata-stripping pipeline. The original upload is never persisted.
Legacy v1's 5 MiB contract is unchanged. Future HTTP intake must bound multipart
request bytes before parsing; that Phase 3 request boundary is not implemented here.

Staging first commits an owned `WRITING` intent, then writes the derivative, then
commits `READY`. Report acceptance consumes a ready owned unexpired stage in its
transaction. Write/ready-commit failure attempts a durable `DELETING` mark and
compensating object delete. A failed compensation leaves a denied, retryable intent.
A crash after intent/object write leaves an unreadable stage with a one-hour deadline.
Unknown aged objects are reconciled after the same grace interval. Rollback of report
acceptance leaves a still-owned ready stage, which expires normally instead of becoming
an untracked object. Attached derivatives expire no later than 30 days from creation
or the parent report deadline. Private reads check owner or case/unit scope, parent
suppression, linkage, expiry, byte count and SHA-256 integrity.

## Retention, deletion and recovery limits

Policies are versioned in `persistence/policies.py`. Default active ceilings are
report/notes/updates/tasks 90 days; derivatives and permitted Gemini/FIRMS/Sentinel
fragments 30 days; unattached media one hour; minimal audit/consumed-key/deletion
ledger 180 days after purge (explicit deletion extends the ledger appropriately).
Settings can shorten content ceilings. There is no raw-provider/composite assessment
JSON column. The normalized source schemas are intentionally narrow Phase 1 seams;
later adapters need reviewed versioned extensions before persisting other products.

Real provider-content retention is OFF by default. Integration tests explicitly
inject synthetic normalized source fixtures. Registry reference URLs/attributions
identify the review targets; they do not certify permission or approve export.
The NASA reference returned 403 to this session's web reader; Sentinel catalog and
Google governance documentation were readable. Owner/provider agreement review
remains pending. There is no live retention or redistribution claim.

Google AQ/weather/forecast fragments have metadata-only
`NOT_RETAINED_BY_POLICY` entries. Their values, content hashes, composite support,
Google-dependent reasons and forecasts have no durable payload command type. SQL
also rejects Google payload/hash persistence. Unknown source types fail closed.
Saved versions declare `pilot_retained_sources_v1`. Google-backed live context and
the scientific rule adapter remain later work; this phase changes neither legacy
numeric rules nor the forecast's advisory separation.

Read projections immediately hide expired/suppressed content. `RetentionService.sweep`
physically removes objects, nulls protected report fields, note/update/task bodies,
source payloads and hashes, clears version input fingerprints, cancels work and
records explicit source redactions/privacy completion. Later source expiries are
still swept after the earliest source has already cleared a version hash. Logical
evidence is immutable except irreversible payload/hash redaction; database triggers
reject replacements and restoration. Consumed idempotency keys become payload-free
tombstones; after their later expiry, the original old key timestamp still prevents
accidental recreation. Minimal relational tombstones are deleted at audit expiry.

Object deletion failure is visible as a failed maintenance pass. The parent stays
suppressed, its key remains available for retry, and no false purge-completion time
is recorded. Deleted filesystem bytes followed by a database rollback are safe to
retry because object deletion is idempotent. No physical-erasure deadline can be
guaranteed during an ongoing storage outage; monitor failures and overdue requests.

**Operational requirement:** schedule the one-shot cleanup command at least once per
minute while local intake is enabled. Read denial does not depend on that scheduler.
Phase 1 provides/tests the bounded maintenance pass; it does not provision a cron
service or hosted worker. Real retained collection must stay disabled until the
hosted private adapter, scheduled cleanup, health/lag alarms and physical purge
rehearsal exist. The local cleanup command rejects nonlocal databases.

Backups/PITR are separate from application deletion. No Neon backup scope, encryption,
replica TTL or seven-day backup expiry was configured or verified here. Before real
collection, verify permitted-content backup retention at most seven additional days,
restricted backup access, and explicit user notice. Never back up original images
or Google content through this store. Maintain the minimal deletion ledger outside
the recovery point being restored. Quarantine every restored database/object set:
apply the latest deletion ledger and elapsed TTL sweeps, reconcile restored objects,
discard all restored sessions/sealed tokens, require fresh login and verify scoped
reads before traffic. This phase proves process restart durability, not disaster
restore or immediate physical erasure from backups. Identity-provider account
erasure is a separate Phase 2/release procedure.

## Local reproduction

The following credentials identify disposable synthetic local data only. No root
`.env` or production URL is loaded. From the repository root:

```sh
docker compose -p airshedos-seva-phase1 -f docker-compose.persistence.yml up -d --wait
cd apps/api
export SEVA_MIGRATION_DATABASE_URL='postgresql+psycopg://seva_test:synthetic_local_only@127.0.0.1:55432/seva_phase1_test'
export TEST_DATABASE_URL="$SEVA_MIGRATION_DATABASE_URL"
.venv/bin/alembic upgrade head
.venv/bin/alembic check
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

The PostgreSQL test fixture refuses any hostname/user/database other than the
documented local synthetic target. It downgrades that test schema to empty, verifies
emptiness, migrates to head and checks model drift; **never point it at valuable data**.
Without `TEST_DATABASE_URL`, PostgreSQL tests explicitly skip instead of substituting
SQLite; that run alone cannot satisfy the phase gate. CI now supplies a PostgreSQL 18
service and the explicit test URL, so persistence gates execute there after push.
CI has not run remotely in this session.

One local cleanup pass, with a dedicated resolved private directory:

```sh
export SEVA_LOCAL_DATABASE_URL="$TEST_DATABASE_URL"
.venv/bin/python -m app.persistence.maintenance --private-root /absolute/private/local-directory
```

This command emits aggregate counts only. Schedule it every minute for local intake;
watch exit status and overdue deletion/expiry state. Use separate migration/runtime/
worker/session roles before hosting; this disposable test database's owner role does
not prove least-privilege grants. Migrations intentionally reject nonlocal connections
in Phase 1; runtime nonlocal connections require `sslmode=verify-full` and bounded
pools. Hosted migration authorization and role/backup rehearsal are release gates.

## Verification record

All results below were executed during this Phase 1 session using synthetic data.
PostgreSQL 18 ran in a dedicated local container named `airshedos-seva-phase1-pg`,
bound to `127.0.0.1:55432`; it was created with `docker run` using the same synthetic
settings as the supplied separate Compose file. No existing Neon schema was touched.

| Required gate | Actual evidence / result |
|---|---|
| Empty database migration | Test fixture downgraded only the guarded local test schema, asserted no domain tables, upgraded to `seva_0001`, verified PostgreSQL version/table/FK presence, and ran `alembic check`: PASS |
| API process restart | Subprocess constructed FastAPI with injected repository, committed a report and review history, printed receipt then exited abruptly with `os._exit(0)` during API lifespan. A different API process read identical report ID/content/history: PASS |
| Second API instance | New engine/session pool and FastAPI instance independently read the committed history: PASS |
| Concurrent revision | Two concurrent writers at the same revision yielded exactly one committed transition/event and one `Conflict`: PASS |
| Atomic rollback | Injected job/event failure left no half-accepted report/case/job/receipt and no unpaired revision: PASS |
| Evidence custody | Exact database JSON row bytes remained unchanged by review; SQL replacement attempts were rejected. Refresh appended a new ID/version, preserved old bytes and invalidated stale case revision: PASS |
| Idempotency | Concurrent duplicates produced one report/case/job/update; exact retry replayed IDs; different body/header conflicted; principal isolation, old unseen keys and deleted-key replay behaved as specified: PASS |
| Retention/deletion | Immediate read suppression, physical report/source/media/body/hash deletion, explicit redaction history, later-source expiry, eventual tombstone deletion and old-key rejection: PASS |
| Media/DB failures | Failed write, ready flush, actual COMMIT, failed compensation, orphan/crash staging and report-acceptance rollback all remained denied/owned and were reconciled. Failed deletion stayed suppressed/retryable without false completion: PASS |
| Expiry under contention | Acceptance waited on a real PostgreSQL media-row lock while the stage expired; after release it rejected attachment and cleanup removed the object: PASS |
| Access/HTTP boundary | Different residents/units, suspended grants and disabled accounts denied; resident projection omitted notes; injected/default app exposed no new v2 routes or public media: PASS |

Final command results:

- `TEST_DATABASE_URL=... .venv/bin/python -m pytest -q`: **561 passed**, two existing
  dependency deprecation warnings, 27.92 seconds. Includes **25** new persistence
  tests and all 536 previous tests, with no skips in the PostgreSQL-enabled run.
- `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .`: PASS, 104 files.
- One-shot `python -m app.persistence.maintenance --private-root ...`: PASS;
  emitted aggregate zero counts on the empty local fixture, with no content logging.
- `npm run lint`, `npm run typecheck`, `npm run build`: PASS.
- `npm run test:e2e`: **58 passed**, 1.5 minutes, local production standalone web
  with current static assets and provider-disabled API. External sources/Maps mocked.
- `python scripts/export_openapi.py`, `npm run generate:api` and repository diff:
  PASS; OpenAPI, frontend types and receiver schema remained byte-identical.
- Six protected contract/scientific SHA-256 fingerprints matched HEAD exactly.
  These checks preserve `MODEL_NOT_ACCEPTED`; they do not measure scientific accuracy.
- Secret scan including builds and document/Git whitespace checks: PASS; final
  file count and cleanup outcome are also recorded in [PHASE_STATUS.md](PHASE_STATUS.md).

Temporary API/web servers were stopped after the browser run. The disposable test
container/private directory are removed at handoff. These are local tests, not a
new deployment, remote CI run, real provider rehearsal or disaster recovery test.

## Deliberate roadmap adaptation and next dependency

Phase 0's inferred ledger placed the worker at Phase 4. The supplied Phase 1 prompt
explicitly reserves the worker for **Phase 5**; that current instruction takes
precedence. This phase adds only scheduling/version seams and cleanup maintenance,
not the analysis worker. Later phase prompts determine the remaining order.

Next is Phase 2: managed identity/session validation, authenticated internal principal
construction, operator-approved memberships and complete backend access isolation.
Keep v2 HTTP exposure off until those checks exist. Phase 3 can consume the private
media/intake seams after access isolation. No resident interface, invitation system,
dashboard redesign, automatic processing, government dispatch, provider availability,
new model, or deployed durable pilot is claimed. `MODEL_NOT_ACCEPTED` and legacy
`pollution_event_v1` remain unchanged.
