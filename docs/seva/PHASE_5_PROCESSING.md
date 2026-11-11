# Phase 5 — durable processing and reliability

11 November 2026 (Asia/Calcutta). Local implementation; hosted activation is pending.
Base revision: `6f071afd10f0ffed024448ac87d3bfae9ec8abc4`.
Working branch: `codex/seva-phase-5`, created from the selected checkout while preserving
all uncommitted Phase 0–4 changes and unrelated presentation/output artifacts. No reset,
other-checkout edits, secret-file copying, push, deployment or production migration.

## Implemented boundary

Report acceptance already inserted a job in the same transaction as the report, case,
idempotency key and initial acknowledgement. That boundary is retained. A new separate
`python -m app.processing` process polls PostgreSQL; the web application starts no
analysis tasks. Reviewer `POST .../enrichments` now returns **202 Accepted**, request ID
and pending/current state. It performs no provider IO. Concurrent repeat clicks join an
active run under the case lock; after completion a reasoned, revision-checked refresh
creates a different request and evidence version. Human review/publication is independent.

`seva_0005` adds lease/heartbeat/due/completion fields, a bounded attempt counter,
requester/unit scope, inert row-lock guard columns and a minimised metrics table
(28 tables total). No new dependency,
broker, cloud migration or custom model. Existing Phase 4 abandoned synchronous runs
are marked failed; older pending runs superseded by an existing evidence version are
cancelled during this **reviewable, not production-applied** migration. Historical
versions/events remain; MANUAL_ENRICHMENT is excluded from worker claiming. A populated downgrade that cannot represent PARTIAL is refused
atomically rather than silently rewriting records.

Workers claim with `FOR UPDATE SKIP LOCKED`; database time controls lease/retry deadlines.
Initial jobs are immediately due without comparing application and database clocks.
Default lease is 120 seconds (explicit 1–600 second configuration); heartbeat runs every
30 seconds or one-third of a shorter lease. Every delivery receives a fresh random token.
Three deliveries maximum per run include crash recoveries. Expired third deliveries
become visible `FAILED / RETRY_EXHAUSTED`. Normal transient retries wait 30 then 120 seconds.
No indefinite retries or exactly-once provider billing is promised.

Report → case → job locks fence source admission, media descriptor reads and publication.
They end before object-store/provider IO. Publication checks the current token, unexpired
lease, active report/owner, approved non-prototype unit, original authorised unit and,
for reviewer refreshes, active requester membership. It freezes a single evidence version
and completes the logical job in the same transaction. Late, repeated, deleted, expired,
withdrawn, re-scoped or revoked work cannot overwrite a successor or resurrect content.
Duplicate delivery is harmless; it does not create a second logical version. A worker
can still die after a billed external call and before committing: recovery may repeat it.

## Scientific and privacy behavior

The former manual collection logic is a shared `EvidenceCollector` used by the worker.
It calls the existing Gemini interpreter, EnvironmentService FIRMS/Sentinel adapters
and deterministic `assess`; there is no second scientific implementation. Gemini
transient timeout/quota/HTTP 5xx failures and explicit provider transport/timeouts are
retryable. Authentication/configuration/schema/safety failures and genuine no-data
outcomes are terminal. Read-time status is independent of review state and exposes
pending/running/partial/failed/cancelled; retry wait projects as pending. Stage attempts
retain their own outcome and safe reason. Text-only visual analysis and durable forecast
are not applicable, including on retries.

**Adaptation from the stage-checkpoint sketch:** this pilot retries a whole attempt only
when it has no usable retained source result. A usable partial result is published once
and an authorised refresh can obtain later data. This avoids a second protected payload
copy in the queue and preserves a coherent source/rule snapshot. Attempts are bounded
by three even when a process crashes. Successful external calls may be repeated after
crashes or a wholly failed run; counters describe admission, not exact billing. There
is no persistent partial provider-response cache or raw response checkpoint.

Frozen versions preserve existing typed source units, observation/retrieval times,
applicability, cache flags, policy versions and source expiry. Google AQ/weather/forecast
values, raw payloads and their derived hashes never enter jobs, metrics or saved evidence.
Google forecast remains a separately requested volatile branch, with 6/12/24-hour window
peaks and no additional corroboration vote. Submission time is an explicitly labelled
proxy; capture time stays unknown unless declared, and remains unverified. Satellite
context cannot establish a local source or violation. No automatic human decision,
reporter update, case merge or government delivery is introduced. MODEL_NOT_ACCEPTED,
protected historical records and offline model research remain unchanged.

Each configured source operation rechecks authoritative case/lease scope and current
cleanup health before an atomic shared PostgreSQL admission debit. The worker shares
`PAID_ANALYSIS` windows with API context operations. Pilot default is 100 admission units
per UTC day, configurable; Gemini reserves 1, FIRMS 2 for its bounded HTTP attempts,
Sentinel 6 as a conservative operation allowance. Cache hits also consume admission.
These are pilot limits/approximate usage units, not measured capacity or precise request,
token or invoice counts. Source SDK retries remain bounded (Gemini one attempt; Earth
Engine max retries zero). No spoofable client/IP/role header controls a debit.

Operational metrics contain source, outcome, elapsed milliseconds, admission units and
creation/expiry, with a job foreign key. No coordinates, descriptions, identities, images,
URLs, credentials or raw exception strings. Request logs contain method/status/duration
only. `python -m app.processing --metrics` is an operator CLI, not a public cross-unit
endpoint; it returns job states, attempts, oldest waiting age and source outcome/latency/
usage totals. An ADMITTED count can exceed completed-call count after failure or crash.
Optional-provider configuration/readiness is not a live availability claim.

Retention removes metrics at 30 days; job/attempt metadata follows the existing report
and audit tombstone lifetime. Jobs hold no protected payloads. Suppression/expiry cancels
work and invalidates leases; normal maintenance removes private derivatives, orphan
objects, evidence payloads/hashes, input hashes and private review/report content, then
expires audit rows/jobs and cascading metrics. Existing session secrets/expired session
links and admissions are purged. There are no presigned access links or persisted export
objects: media and exports are freshly scoped reads; browser export object URLs are
revoked. Expiry guards operate even when cleanup is down. Cleanup health gates paid work.
A restored expired report cannot be processed; a backup missing a recent deletion ledger
cannot be made safe by a content hash. Before any restore is enabled, an operator must
reconcile the deletion ledger, invalidate restored leases, run complete cleanup and
verify private-object expiry. Hosted backup/ledger/restore rehearsal remains a Phase 6
release gate, not a claimed completed live capability.

## Execution and hosting

See [development instructions](../DEVELOPMENT.md). Runtime requires explicit `APP_MODE=pilot`
and `SEVA_WORKER_DATABASE_URL`, schema 0005, a separately scoped worker role and current
retention maintenance for configured sources. It needs no Auth0 session-secret access;
[worker grants](../../apps/api/scripts/worker_roles.sql) are tested against PostgreSQL. Guard-column grants allow row locking without granting
worker access to reactivate revoked memberships or suppressed reports.
Use a read-only private-object credential for worker reads where the host supports it;
cleanup writes/deletion belong to a separate maintenance identity.

`--once` handles one due delivery; the normal command polls every two seconds, finishes
bounded work on SIGTERM/SIGINT and exits. SIGKILL is recovered by lease expiry.
[docker-compose.worker.yml](../../docker-compose.worker.yml) supplies a separate Docker
service with restart policy and 115-second graceful shutdown; its private environment
file must be explicitly selected. It has no production local-storage fallback or fake
principal/login route. Synthetic subprocess tooling lives only under tests, excluded
from the application image.

The checked-in `render.yaml` still defines only a prototype web service. No account or
worker service was provisioned/inspected as live. Render supports a continuous separate
[background worker service](https://render.com/docs/background-workers); a disabled,
review-only [worker example](render-worker.example.yaml) records a supported hosting path.
Applying that example can incur charges and needs separate authorisation, pilot DB,
private storage, credentials, cleanup scheduler and the hosted recovery rehearsal.
Running inside an ephemeral web request is not an alternative. A host supporting only
request handlers must run this worker on an explicitly selected continuous container
host; do not declare durable processing live until that host is established.

Implementation references checked for the installed stack: PostgreSQL 18
[SELECT / SKIP LOCKED](https://www.postgresql.org/docs/18/sql-select.html), SQLAlchemy 2.1
[transaction contexts](https://docs.sqlalchemy.org/en/21/orm/session_transaction.html).

## Verification

Final local command results are recorded in [PHASE_STATUS.md](PHASE_STATUS.md):
**625 backend tests**, **5 identity tests**, **4 resident browser journeys**,
**2 authority browser journeys**, and **62 existing browser regressions** pass.
Ruff (138 files), frontend lint/typecheck/production build, schema/type regeneration,
secret scan, protected-record hashes and local document links pass. Two existing
FastAPI/Starlette test dependency deprecations remain; no local gate is waived.
The disposable schema was recreated after refining the development migration so
the final full pass tested the final schema from empty through downgrade/reapply.
Required synthetic PostgreSQL evidence includes concurrent distinct claims; actual
SIGKILL during collection and restart recovery; lease expiry/fencing; injected duplicate
delivery; three-attempt exhaustion; separate Gemini/FIRMS/Sentinel failures preserving
independent partial results; quota rejection before invocation and concurrent-worker
shared quota; immutable refresh versions; delete/expire/withdraw/revoke during IO;
expired-restored queue entries; physical media/payload/metric cleanup; restricted-role
publication with session-secret reads denied; safe metrics/request logs; and resident/
reviewer availability while analysis fails. Existing browser journeys now explicitly
run the separate test worker after enqueueing; sign-in/permissions remain real signed
local OIDC/SDK/BFF/FastAPI/PostgreSQL flows, not mocked page guards.

No paid provider call, live sign-in, remote CI run, live storage/cleanup check, government
receipt, measured user benefit, production activation or research rerun is claimed.
Phase 6 consumes these local outputs for release/security/privacy/restore hardening;
comprehensive visual redesign remains Phase 7.
