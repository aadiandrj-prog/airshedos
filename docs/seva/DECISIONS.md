# Phase 0 implementation decisions

Date: 10 November 2026 (IST). Contract: `seva_pilot_v1`.
These are implementation choices for later phases; none installs a dependency,
provisions a service, changes the live application, or starts Phase 1.
That statement describes the original Phase 0 decision record; subsequent local
implementations are tracked below and do not imply deployment.
The [blueprint](IMPLEMENTATION_BLUEPRINT.md) is the detailed normative contract.
The [status record](PHASE_STATUS.md) distinguishes design from implementation.

Phase 6 is recorded in [PHASE_6_VALIDATION.md](PHASE_6_VALIDATION.md). It makes recovery
quarantine executable with an out-of-band UUID and canonical current erasure manifests,
separate worker/cleanup health, approved triage readiness, expiry clearing and withdrawn
media denial. Paid resident context now uses an owned accepted report with approved
case routing and stored coordinates; pre-submit context makes no provider request.
Pilot maps require an explicit build-time purpose flag. Runtime dependency
advisories received targeted fixes; one development-only minimatch advisory remains
tracked without a forced major override. Twelve synthetic scenarios and a matched-task
protocol are prepared, with no field cases or participant evidence. Hosted erasure-journal/
backup/identity/storage/worker checks and recruitment remain external release gates.

Phase 5 supersedes the temporary synchronous enrichment execution described below.
[PHASE_5_PROCESSING.md](PHASE_5_PROCESSING.md) records the separate PostgreSQL worker,
fenced leases, bounded whole-attempt retries, partial immutable publication, safe metrics,
source-operation admission, retention and explicitly pending hosted worker activation.
No new broker, paid provisioning, government transport or model training was introduced.

Phase 4's human review and bounded enrichment implementation is recorded in
[PHASE_4_AUTHORITY.md](PHASE_4_AUTHORITY.md). It preserves historical review meanings,
adds explicit reasoned reopening, keeps publication separate and freezes new evidence
versions. `MANUAL_ENRICHMENT` is distinct from worker jobs; source retention approval
and fresh cleanup health gate retained live collection. Optional context is now a
CSRF-protected POST with no coordinate query URLs. A new metadata-only pilot packet v2
preserves the legacy export contracts. No worker or government transport is introduced.

Phase 3's actual resident journey and scoped prerequisites are recorded in
[PHASE_3_RESIDENT.md](PHASE_3_RESIDENT.md). It adds an authenticated introduction,
commit-only intake/receipt recovery, own list/detail, optional private derivatives
through maintained boto3/R2, and append-only information-request replies. New
`seva_0003` tables preserve original reports/evidence and explicit purge exceptions.
The host storage adapter is gated by operator approval; no public bucket URL or
production local fallback is provided. A hosted bucket/scheduler and real managed
sign-in remain external gates. General context stays optional/volatile and outside
acceptance. The worker, reviewer dashboard and visual redesign remain later work.

Phase 2's actual implementation, security refinements and remaining live checks are
recorded in [PHASE_2_ACCESS.md](PHASE_2_ACCESS.md). It implements the selected Auth0
SDK/database-session design, uses atomic SDK store updates and separate ciphertext
grants, and authenticates offline provisioning through a separately approved database
management login. Targets must already have exact verified issuer/subject identities;
no public bootstrap or account-linking-by-email is introduced. Invitations are pending
reviewer proposals, not emailed messages or grants. Pilot export is metadata-only
`pilot_case_packet_v1` until payload redistribution is approved. Default prototype
behavior remains separate; explicit pilot mode blocks legacy v1 access. The targeted
Next.js 16 security update is a prerequisite, not a broad dependency modernization.

Phase 1 implementation and refinements are recorded in
[PHASE_1_PERSISTENCE.md](PHASE_1_PERSISTENCE.md). Current source remains based on
`6f071af`, on local `codex/seva-phase-1` with uncommitted changes. The supplied
Phase 1 prompt reserves the analysis worker for Phase 5, overriding the earlier
inferred phase numbering. Phase 1 implements only its transactional job/version
seams and explicit local retention maintenance. Managed identity, public v2 routes,
hosted storage, real provider retention and deployment remain pending. Evidence
arrival advances case revision as well as evidence sequence, so a stale reviewer
cannot silently act against a different latest version. PostgreSQL row locks are
explicitly ordered report then case, followed by rechecking membership under locks.

## ADR-001 — One selected checkout and a local phase branch

Use `/Users/aadityajain/Technical Assessments/Onboarding/Google Build Week`.
Baseline HEAD is `6f071afd10f0ffed024448ac87d3bfae9ec8abc4`, with no tracked
modifications at entry. It includes remote main `142dfc1`; remote main was read
again this session. Its additional commit records provider recovery. No source
reconciliation or copying is required. Work is on `codex/seva-phase-0`, created
locally at the same commit. Preserve unrelated untracked decks/output. No other
checkout, secret file, live record, remote branch or deployment is changed.

## ADR-002 — Two route spaces, one domain

Choose `/resident` and `/authority`; keep the current Next.js and FastAPI apps.
FastAPI owns reports/cases/authorization. Next.js provides managed login and a
same-origin BFF. Use `/api/v2` for the new domain instead of overloading the v1
image-analysis/demo shapes. A narrow functional UI precedes Phase 7 polish.
Do not build a second backend or split microservices.

## ADR-003 — Managed OIDC with Auth0's official Next.js SDK

Choose Auth0 Universal Login, Authorization Code + PKCE, and
`@auth0/nextjs-auth0` v4 on Next.js 16. Official SDK documentation currently
identifies v4.33.0 and supports Next.js 16 proxy integration, custom database
session storage and logout hooks. Pin an audited stable release when Phase 2
adds it; it is not installed now. Use the SDK's maintained protocol handling;
do not implement a password system or turn role selection into authentication.

Alternatives considered: an SPA token/localStorage flow increases exposed token
surface and cross-origin complexity; a second authentication/database platform
would add an unnecessary migration; self-managed passwords add avoidable risk.
An Auth0 tenant/application/API and exact callback configuration are external
dependencies, not grounds for blocking local code and fixture tests.

References: [official SDK](https://github.com/auth0/nextjs-auth0),
[database sessions](https://github.com/auth0/nextjs-auth0/blob/main/EXAMPLES.md#database-sessions).

## ADR-004 — Server sessions and independently verified API identity

Use SDK database sessions in PostgreSQL with sealed token data and a separate
random app-session binding. Browser cookies are Secure/HttpOnly/host-only;
access/refresh tokens remain server-side. Disable the SDK access-token endpoint.
Next.js uses a restricted `pg` session adapter; Alembic owns its DDL. FastAPI
checks active session metadata bound to the JWT subject and cannot read tokens.

FastAPI validates Auth0 custom-API RFC 9068 access tokens with `PyJWT[crypto]`:
fixed RS256, issuer/audience/client, signed JWKS and required/temporal claims,
including access-token `typ`. A valid ID token is still rejected. No token-derived
unit role is authoritative. The BFF checks session-bound CSRF plus exact Origin,
strips user-provided identity headers, and forwards only allowlisted operations.

Local logout/revocation is immediate on the next API action, even if a token
has not expired. Upstream-only suspension is not promised immediate without
verified back-channel support; local account/session suspension and the eight-
hour absolute session ceiling are explicit controls. Authentication outages
fail closed. Test principals/JWKS are factory-injected and never public bypasses.

References: [token profiles](https://auth0.com/docs/secure/tokens/access-tokens/access-token-profiles),
[PyJWT](https://pyjwt.readthedocs.io/en/stable/usage.html),
[SDK token-endpoint control](https://github.com/auth0/nextjs-auth0/blob/main/src/server/client.ts).

## ADR-005 — Operator-approved local unit membership

Application PostgreSQL stores pending/active/suspended/revoked unit membership.
Operator approval of an exact verified issuer/subject is required for reviewer
and unit-admin grants. Unit admins can propose membership and manage own-unit
assignments, never approve their own or another unit's grants. Operator bootstrap
and cross-unit routing use an authenticated offline command with audit. There
is no universal operator case-read privilege without separate unit membership.
Every object/list/export/media query and mutation checks current ownership/unit
scope; mutation checks occur transactionally. Email-domain matching is excluded.

## ADR-006 — PostgreSQL, SQLAlchemy, psycopg and Alembic

Choose PostgreSQL 18, SQLAlchemy 2.1, psycopg 3 and Alembic 1.x. The official
SQLAlchemy site identifies 2.1 as current and 2.0 as maintenance; this is a new
integration, not an unrelated upgrade to an existing ORM. Exact stable versions
are resolved and locked during Phase 1. No SQL package is installed in Phase 0.
Separate migration, API, worker and session roles/connections. Migrations use a
direct connection; runtime uses bounded TLS pools. No production `create_all`.

The historically empty Neon PostgreSQL project is the intended database candidate.
Its present schema/permissions/backup window were not inspected this phase.
No production migration is authorized. Local disposable Postgres tests are
mandatory for constraints, transactions and locking; SQLite is not sufficient.

References: [SQLAlchemy](https://docs.sqlalchemy.org/en/21/intro.html),
[Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html),
[Neon connectivity](https://neon.com/docs/guides/sqlalchemy).

## ADR-007 — Durable report first, exactly one case

Create report, unique related case, initial receipt and PostgreSQL job in one
transaction, before analysis. Report facts, processing attempts, evidence
versions, review events and reporter updates are separate records. A provider
failure is a processing result, never loss of an accepted report. Case IDs are
random stable IDs, not the current content-derived assessment ID. No automatic
merge. Client idempotency is scoped to authenticated owner/operation/key; same
body replays IDs, a different body conflicts. Retain consumed-key tombstones
through privacy deletion for 180 days. An unseen key also needs a stable
`Idempotency-Key-Created-At` no older than 24 hours, so an expired tombstone does
not make an accidental old retry a new acceptance. These times describe retry
intent, never the report's capture time.

## ADR-008 — PostgreSQL-backed worker and real host dependency

Use a PostgreSQL jobs table as transactional outbox and queue, plus one worker
entry point in the existing API codebase. Implement SKIP LOCKED claims, leases,
heartbeat/fencing, bounded stage retries and unique result/version finalization.
At-least-once processing can duplicate external requests after a crash; it must
not duplicate accepted reports, versions or publications. No Redis/Celery service
is necessary at initial pilot volume. FastAPI BackgroundTasks cannot provide
durable job acceptance.

Propose a separate Render Background Worker using the same image and database.
The present free Render web service sleeps and is not a continuous worker plan.
Suitable hosted worker provisioning requires separate owner authorization; it is
not created now. Local worker development and crash tests remain possible.

References: [PostgreSQL locking](https://www.postgresql.org/docs/18/sql-select.html#SQL-FOR-UPDATE-SHARE),
[Render workers](https://render.com/docs/background-workers),
[free limitations](https://render.com/docs/free).

## ADR-009 — Text-only reports and unchanged scientific boundaries

Text-only intake is valid. VISUAL is NOT_APPLICABLE and no Gemini call occurs.
Its frozen assessment says no visual hypothesis / insufficient advisory support,
not no pollution. Retain declared time/place; verified facts append separately.
Existing numeric corroboration thresholds stay unchanged and explain eligible
inputs. Satellite columns are contextual; missing detections cannot clear a
report. Google outlook stays separate with 6/12/24-hour window peaks. Preserve
`MODEL_NOT_ACCEPTED`; no historical research extraction/training/test evaluation.

## ADR-010 — Private derivatives through an adapter

Select boto3 and private S3-compatible Cloudflare R2 storage for pilot media.
Use a local private-filesystem adapter and fake S3 for deterministic tests.
Never use Render ephemeral disk as a production fallback. Stage only cleaned
derivatives with random keys, reconcile orphan uploads, and discard originals
and request spools immediately. Authorized backend/BFF streams enforce ownership,
unit scope, linkage and expiry. No public URLs, r2.dev, public custom domain or
browser-presigned object links. Media coordinates/time remain declared facts.

The new BFF intake uses a 4,000,000-byte image ceiling plus 64 KiB multipart
overhead because Vercel documents a 4.5 MB request limit. Existing direct v1
5 MiB behavior is unchanged. Oversized images do not prevent text submission.
Private bucket, credentials/region and hosted boundary tests remain external.

References: [R2 API](https://developers.cloudflare.com/r2/api/s3/api/),
[bucket controls](https://developers.cloudflare.com/r2/buckets/public-buckets/),
[Vercel limits](https://vercel.com/docs/functions/limitations).

## ADR-011 — Retention is source-specific, with no durable Google copy

Propose active-content defaults: report/case/notes/updates 90 days, attached clean
media and Gemini/FIRMS/Sentinel fragments 30 days, unattached media one hour,
minimal audit 180 days. Configure shorter values as needed. Backups of permitted
content may retain encrypted bytes for an additional disclosed seven-day window;
owner confirmation and a restore-deletion ledger are required. Do not call these
defaults legal compliance or claim that a database backup plan is configured.

Google's published non-EEA source-specific terms give one-hour caching for
current AQ/hourly forecast/current Weather. A PostgreSQL TTL would still leave
copies in PITR/backups. Initial pilot therefore uses request/volatile-cache-only
Google content (15-minute cache), with no stored values/hashes/dependent support
or forecast in evidence, jobs, backups or exports. Durable evidence explicitly
uses `pilot_retained_sources_v1`; Google fragments are NOT_RETAINED_BY_POLICY.
Separately labeled live context cannot alter frozen support. This is an explicit
change from the legacy in-memory full snapshot, not a hidden source substitution.
Unknown source permissions default to no persistence. Owner/provider agreement
review is required before retaining additional content or redistributing it.

Reference: [Google source-specific terms, sections 2 and 21](https://cloud.google.com/maps-platform/terms/maps-service-terms).

## ADR-012 — Immutable facts with explicit redaction exceptions

Freeze logical evidence versions and append review events. Store permitted
expiring content in separately purgeable fragments; read-time guards hide expired
content immediately and a worker physically deletes it. Redaction events identify
expired/deleted source availability without preserving the protected payload or
hash as a substitute. Derived copies expire with their source. Refresh creates
a new version. Deletion suppresses access/cancels work immediately and purges
content within 24 hours or earlier source expiry. Restores stay quarantined until
deletion tombstones/elapsed TTLs are applied. No ordinary reviewer undelete or
silent historical recomputation. Retention defaults are not custody guarantees.

## ADR-013 — Private notes and deliberate reporter publication

Keep existing internal review states and transition rules. Reporter status is
a separate safe publication stream; only the initial receipt is automatic.
Internal acknowledgment, closure, processing success or a note never publishes
an update implicitly. Separate Pydantic projections and database records prevent
internal-note/identity leakage. Corrections append or explicitly redact. A field
follow-up describes pilot reviewer activity, not government attendance/dispatch.

## ADR-014 — Explicit legacy and export version boundary

Keep `pollution_event_v1` unchanged in isolated synthetic demos. Its mandatory
Gemini fields cannot honestly represent text-only/retention-redacted pilot cases.
Use a new `pilot_case_packet_v1` manual export with nullable interpretation and
fragment states, default omission of private notes/identity/media and all Google
content/derived copies. Every export rechecks unit scope and expiry. All legacy
v1 domain routes return 404 in pilot mode, so they cannot bypass the new domain.
Demo mode refuses real pilot storage/provider credentials and is isolated.
No automatic migration of ownerless ephemeral demo data.

## ADR-015 — Evidence of completion and scope discipline

Fresh tests were run for Phase 0; old 536/58 records are historical until rerun.
Current successful synthetic tests verify engineering behavior, not provider
uptime, scientific accuracy, recruited users or measured benefit. Full pytest
includes existing synthetic estimator regression checks, not historical model
research. Use signed synthetic JWKS/local Postgres/fake providers/media for later
tests; missing external credentials leave live checks pending, not simulated.
No runtime feature or redesign is needed to recover this passing baseline.

## Open external dependencies and owner decisions

| ID | Required before | Missing or unverified item | Local development fallback |
|---|---|---|---|
| EXT-01 | Managed login rehearsal | Auth0 tenant, Regular Web App, custom API RFC 9068 audience/client, callback/logout/refresh/backchannel configuration | Signed fixture JWKS and factory-injected principals |
| EXT-02 | Hosted DB migration | Owner-selected Neon target, verified schema, scoped TLS roles, migration permission and backup/PITR window | Disposable PostgreSQL 18 |
| EXT-03 | Hosted private media | Private R2 bucket, credentials, region and lifecycle | Temp private filesystem/fake S3 |
| EXT-04 | Hosted async processing | Approved suitable Render Background Worker plan and deploy authorization | Separate local worker process |
| EXT-05 | Any real-data collection | Owner-approved retention/backup/regions, privacy/terms notices, source permitted use, unit roster/triage/operator and budgets | Synthetic data only |
| EXT-06 | New live provider claims | Separately recorded authenticated provider checks; existing local Google key is documented as production-IP restricted | Provider fakes, explicit unavailable results |
| EXT-07 | Wider provider snapshot/export | Contract-specific permission and expiry/backup design; no arbitrary extension of Google content TTL | Volatile live context, safe unavailable/tombstone fields |

No open item requires choosing a library interactively. These are release/live
dependencies; Phase 0 can be locally verified without them. Subsequent contract
changes append an ADR with reason and affected acceptance checks.


## Phase 7 implementation note — one visual language

11 November 2026, base `6f071af`, branch `codex/seva-phase-7`.
The supplied resolved visual direction supersedes the earlier temporary dark/green UI
for pilot routes. [DESIGN_DIRECTION.md](DESIGN_DIRECTION.md) records scoped light tokens,
locally hosted Geist, the public editorial composition, resident form/timeline and denser
unit rail/evidence/action layout. Original generated HTML is stored only as reference.
Prototype mode remains isolated, all API/scientific/visibility rules stay unchanged.
Necessary UI fixes cover filter hydration, loading admission controls, map fallback height
and cold-route sign-in spacing. No backend architecture expansion was needed.
See [PHASE_7_POLISH.md](PHASE_7_POLISH.md) for actual rendered evidence and limitations.
