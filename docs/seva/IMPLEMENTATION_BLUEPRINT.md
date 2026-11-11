# AirshedOS resident and reviewer implementation blueprint

Contract: `seva_pilot_v1`. Frozen for implementation on 10 November 2026 (IST).
Status: **DESIGN CONTRACT; capabilities below are not implemented by Phase 0.**
Phase 1's actual local implementation/limits are tracked separately in
[PHASE_1_PERSISTENCE.md](PHASE_1_PERSISTENCE.md) and [PHASE_STATUS.md](PHASE_STATUS.md).
The current Phase 1 prompt reserves the analysis worker for Phase 5; earlier inferred
phase numbering does not authorize starting it here.
Phase 2 identity/isolation implementation, scoped API surface and configuration/live
limits are recorded in [PHASE_2_ACCESS.md](PHASE_2_ACCESS.md). This blueprint remains
the target contract; a described later-phase interface is not proof of deployment.
Source baseline: `6f071afd10f0ffed024448ac87d3bfae9ec8abc4`.
Phase 4’s actual human workflow/manual enrichment, explicit state extension and
remaining live gates are recorded in [PHASE_4_AUTHORITY.md](PHASE_4_AUTHORITY.md).
Automatic worker processing remains Phase 5; the original inferred numbering below
does not authorize a worker in Phase 4.
Phase 3's locally verified resident interface/private upload adapter is recorded in
[PHASE_3_RESIDENT.md](PHASE_3_RESIDENT.md). The introduction route supersedes the
original `/resident` redirect target. Hosted identity/storage checks remain pending;
the later reviewer/worker/release capabilities below are still target contracts.
Read [decisions](DECISIONS.md), [phase status](PHASE_STATUS.md), and the
[fresh baseline](PHASE_0_BASELINE.md) before implementing a phase.

## 1. Product boundary and minimum release

Keep the existing Next.js/React/TypeScript application and FastAPI/Pydantic
backend. Add two route spaces over one report/case domain. A signed-in resident
submits a text report, optionally with one image, and follows only their own
reports. An operator-approved reviewer works on cases assigned to their unit.
The reviewer can inspect advisory evidence, add internal notes, record a pilot
field follow-up, and deliberately publish a separate update to the reporter.
There is initially exactly one case per report, including reports awaiting or
failing processing. No automatic merging, official dispatch, public case feed,
external messaging, custom model deployment, or new hardware is included.

Acceptance is durable before any AI or environmental-provider request. Unknown
capture time stays unknown. Claimed location/time and reviewer-verified facts
remain distinct. Text-only reports are first-class inputs. Scientific rules,
native units, uncertainty, `MODEL_NOT_ACCEPTED`, isolated research, and the
separate Google forecast are preserved. Forecast horizons are window peaks.

Comprehensive UI polish belongs to Phase 7. Earlier phases reuse current
components with functional forms, accessible labels, keyboard operation,
390px usability, and explicit loading/error/partial states.

## 2. Routes and API ownership

These are target routes, not current routes. FastAPI owns domain authorization
and state transitions. Next.js owns OIDC/session handling and the BFF (backend
for frontend). Route-group names do not themselves enforce access.

| Website route | Required access | Purpose |
|---|---|---|
| `/` | Public | Entry links, prototype description; no individual reports |
| `/privacy`, `/terms` | Public | Approved notices before real collection |
| `/resident` | Resident session | Redirect to own reports |
| `/resident/reports` | Resident session | Own report summaries only |
| `/resident/reports/new` | Resident session | Text and optional image intake |
| `/resident/reports/[reportId]` | Owning resident | Own receipt and published updates |
| `/authority` | Active approved unit membership | Unit selection/assigned case entry |
| `/authority/cases` | Active membership in selected unit | Scoped queue |
| `/authority/cases/[caseId]` | Active membership in owning unit | Evidence, notes, review and follow-up |
| `/authority/unit` | Approved unit admin | Own-unit assignments and membership requests |
| `/demo` | Isolated synthetic demonstration | Existing fictional workflow after explicit migration |
| `/auth/login`, `/auth/callback`, `/auth/logout`, `/auth/backchannel-logout` | SDK-controlled | Managed authentication lifecycle |

Browser domain requests use same-origin `/api/app/v2/...`; allowlisted BFF
handlers forward to the corresponding FastAPI `/api/v2/...` path. An extra
`GET /api/app/csrf` returns a session-bound application CSRF nonce. No generic
URL-forwarding proxy or browser access-token endpoint is enabled.

| FastAPI operation | Contract and authorization |
|---|---|
| `GET /api/v2/me` | Verified principal; own safe profile and active memberships |
| `POST /api/v2/resident/media` | Own staged derivative; authenticated, bounded upload |
| `POST /api/v2/resident/reports` | Own durable acceptance; mandatory `Idempotency-Key` |
| `GET /api/v2/resident/reports` | SQL predicate `reporter_user_id = principal.id`; paginated |
| `GET /api/v2/resident/reports/{report_id}` | Same ownership predicate; reporter-safe projection |
| `POST /api/v2/resident/reports/{report_id}/withdraw` | Owner; cancels future processing; no fabricated resolution |
| `POST /api/v2/resident/reports/{report_id}/deletion-requests` | Owner; durable privacy request and immediate access suppression |
| `GET /api/v2/resident/media/{media_id}` | Owner AND unexpired attached/staged media |
| `GET /api/v2/authority/units/{unit_id}/cases` | Active approved membership in unit; unit-scoped SQL |
| `GET /api/v2/authority/units/{unit_id}/cases/{case_id}` | Case assignment and membership must both match |
| `POST .../cases/{case_id}/review-events` | Same scope, allowed transition, expected revision |
| `GET/POST .../cases/{case_id}/internal-notes` | Same scope; private-only response models |
| `GET/POST .../cases/{case_id}/field-follow-ups` | Same scope; pilot follow-up, no official dispatch |
| `POST .../cases/{case_id}/field-follow-ups/{follow_up_id}/events` | Same scope/linkage/revision; assigned reviewer or unit admin records completion |
| `POST .../cases/{case_id}/reporter-updates` | Same scope; explicit preview/publish and expected revision |
| `POST .../cases/{case_id}/evidence-refreshes` | Same scope; enqueue a new version, never overwrite |
| `GET .../cases/{case_id}/evidence/{version_id}` | Same scope AND fragment retention checks |
| `GET .../cases/{case_id}/live-context` | Same scope and quota; request-scoped Google context/outlook, no durable snapshot |
| `GET .../cases/{case_id}/media/{media_id}` | Same scope, case linkage AND media retention |
| `POST .../cases/{case_id}/assignments` | Own-unit admin; active assignee in same unit |
| `GET .../cases/{case_id}/export` | Same scope; retention-safe `pilot_case_packet_v1` only |
| `GET/POST /api/v2/authority/units/{unit_id}/membership-requests` | Own-unit admin can propose, never approve a grant |

In the table, `...` expands exactly to
`/api/v2/authority/units/{unit_id}`. Explicit Pydantic requests reject extra
fields. Backend fills owner, actor, unit permissions and server timestamps;
client `user_id`, `role`, `approved`, `actor` or inferred unit claims are never
accepted as authority. Unknown and out-of-scope object IDs return the same 404.
Missing authentication returns 401; a known principal lacking a route-level
capability returns 403. Stale revisions/idempotency conflicts return 409.

Operator unit creation/approval and cross-unit routing use an authenticated
offline management command, not a new public operator UI in the first release.
List counts, filters, joins, exports and media must use the same scope predicates.
`/health` remains a sanitized process check. Target `/ready` verifies database
connectivity, schema revision and required application configuration, without
calling providers. An offline worker does not block durable intake readiness;
queue age/worker heartbeat are separately monitored. Phase 1 adds repositories
and migrations, not publicly exposed unauthenticated v2 domain routes.

## 3. Access matrix and trusted assignments

The same person may be a resident and a reviewer. Identity is `(issuer, sub)`,
never email matching. Resident capability follows an active authenticated local
account. Review capabilities come only from active PostgreSQL `unit_memberships`.

| Operation | Anonymous | Resident | Reviewer | Unit admin | Operator |
|---|---|---|---|---|---|
| Submit / track / withdraw own report | No | Own | Own resident reports | Own resident reports | Own resident reports |
| Read someone else's resident view | No | No | No | No | No |
| Read case evidence/private media | No | Own media only | Assigned unit | Own unit | Only with separate active unit membership |
| Internal note / review / publish / field follow-up | No | No | Assigned unit | Own unit | Only with separate active unit membership |
| Assign a case to another reviewer | No | No | No | Active reviewer in own unit | Unit-routing administration only |
| Propose membership | No | No | No | Own unit, pending request | Any approved pilot unit |
| Activate/grant reviewer or unit admin | No | No | No | No | Explicit verified-subject approval |
| Suspend reviewer membership | No | No | No | Reviewers in own unit; no admin escalation | Yes |
| Transfer owning unit | No | No | No | Request only | Audited routing action |

Operator is a separately bootstrapped privilege tied to an exact verified OIDC
subject through an offline command and audit event. Unit-admin powers never
extend beyond their unit. Reactivation after suspension requires operator
approval. An invitation, email domain, token role claim or frontend toggle is
not a grant. Check active membership and local account status on every request,
without a long-lived authorization cache. Mutations recheck inside the write
transaction so revocation cannot be bypassed by a stale page.

`PILOT_TRIAGE_UNIT_ID` names an operator-approved intake unit. New cases route
there when configured; prototype coordinate rectangles remain informational.
If routing configuration is absent, accept an unassigned case durably. Only the
operator's minimal routing queue can list unassigned IDs, submission time and
routing state, without description/identity/exact coordinates. It can assign a
case to an approved unit. No global reviewer queue is permitted. Pilot release
requires a configured staffed triage unit; no recruitment is claimed.

## 4. Authentication and server trust boundary

Select Auth0 Universal Login / OIDC Authorization Code flow with PKCE and the
official `@auth0/nextjs-auth0` v4 SDK. Use Next.js 16 `src/proxy.ts` integration
plus server Route Handlers. Configure SDK-managed PostgreSQL database sessions,
not its default token-bearing encrypted-cookie session storage. The Node `pg`
adapter implements the documented `SessionStore`; Alembic owns table DDL.
These dependencies are selected, not installed in Phase 0.

1. The SDK validates the OIDC exchange, state, nonce and PKCE. Exact callback and
   logout origins are configured; callback errors expose no provider payload.
2. The browser receives a host-only `Secure`, `HttpOnly`, `SameSite=Lax` session
   cookie with `Path=/` and no Domain. Use the SDK-supported cookie configuration
   and `__Host-` naming in HTTPS environments. Local HTTP is a separately explicit
   localhost-only setting, forbidden by production configuration validation.
3. Persist access/refresh tokens only in encrypted server session records, using
   a maintained encryption primitive with a rotated server key. Neither tokens
   nor the server-only `app_session_id` appear in React props, browser storage,
   analytics, logs or errors. Set `enableAccessTokenEndpoint: false`; return an
   allowlisted local profile instead of exposing the full SDK profile/session.
4. The BFF validates its session and an exact allowed Origin plus session-bound
   CSRF nonce for writes. Also reject cross-site Fetch Metadata where supplied.
   The SDK separately handles OIDC callbacks and validated back-channel logout.
5. The BFF gets a custom-API access token server-side with configured
   `AUTH0_AUDIENCE`. It strips incoming Authorization, Cookie and identity/unit/
   session headers; it creates its own Authorization bearer header and
   `X-AirshedOS-Session` from the trusted server session. Upstream paths/methods
   are allowlisted and bounded. No client-chosen upstream URL is accepted.
   The planned API identifier is `urn:airshedos:pilot-api`; request scopes are
   `openid profile offline_access access:airshedos`. FastAPI requires the
   `access:airshedos` scope as well as its own domain permissions.
6. FastAPI independently verifies the token with maintained `PyJWT[crypto]` and
   configured issuer JWKS: RS256 only; valid signature; required `iss`, `sub`,
   `aud`, `exp`, `iat`, `jti`, `client_id`; `nbf` when supplied; issuer exact match;
   AirshedOS audience; allowed BFF client ID; maximum 60-second clock skew.
   Configure Auth0's RFC 9068 profile and require `typ=at+jwt` (or its RFC media
   type spelling `application/at+jwt`). ID tokens, Management API/userinfo tokens,
   unknown issuers/algorithms, missing claims and wrong audiences fail closed.
   Token headers never choose JWKS URLs. Unknown-key refresh is rate-bounded.
7. The token is necessary but insufficient: FastAPI checks the supplied random
   app-session credential against an active server record bound to the token's
   issuer/subject, expiry and local user status. Session IDs are not trusted as
   identity. Database/session failures deny access. Reviewer permissions are
   then read from local memberships, not JWT role claims. Tokens issued without
   an application session cannot call resident/reviewer APIs.

Create `app_session_id` only on validated login, retaining it on refresh, and
store its binding as part of `SessionStore.set` in the same database transaction
as the sealed SDK session. FastAPI reads session metadata only; it cannot read
token ciphertext. Next.js has a least-privilege session-store database role,
not unrestricted domain-table write access. Python owns domain mutations.
Only a validated new login can create a new app-session binding. Refresh/session
updates require an existing unrevoked binding and never clear `revoked_at` or
recreate a deleted binding. Keep revocation tombstones through the maximum
session/token lifetime; test concurrent logout and refresh to prevent resurrection.

Pilot defaults: eight-hour absolute session, 30-minute idle limit, custom-API
access-token lifetime at most ten minutes. Refresh uses managed rotation and
reuse detection. Logout revokes the local session before clearing the cookie;
the still-unexpired access token then fails the backend session check. Operator
account disablement revokes local sessions/memberships immediately. Implement
SDK back-channel logout verification and `deleteByLogoutToken` where tenant
support exists; do not claim immediate upstream-only suspension detection if
that integration is unavailable. An eight-hour local ceiling is the stated
residual bound; operator local suspension is the emergency control.

No password implementation, unsigned JWT parsing, default production principal,
email-based officer promotion, wildcard preview callback or public auth bypass.
Tests inject explicit principals and locally signed test JWKS through the app
factory; fixture identity code must not be routable or selectable in production.

## 5. Shared domain and response projections

Use UUIDv4 opaque IDs; IDs confer no permission. All timestamps are aware UTC.
Case identity is independent of assessment content, and `cases.report_id` is
UNIQUE and NOT NULL. Avoid a content-derived assessment ID as case identity.

| Entity | Minimum fields / rules |
|---|---|
| `users` | id, issuer, subject UNIQUE pair, active, minimal display fields, created_at; no provider role grants |
| `units` / `unit_memberships` | id/name/prototype marker; user/unit/role, pending/active/suspended/revoked, approver and time; audited grants |
| `auth_sessions` | opaque SDK key, app-session binding, issuer/sub, created/idle/absolute expiry, revoked_at, sealed token data; restricted DB grants |
| `reports` | id, reporter_user_id, accepted_at, immutable description (1–2,000 characters), declared category, reported lat/lng, optional declared_capture_at, capture_time_basis, optional media_id, receipt ID, withdrawn/deletion state, content_expires_at |
| `cases` | id, unique report_id, assigned_unit_id nullable, assigned_reviewer_id nullable, review_state, revision, latest_evidence_version_id nullable, created_at; assignment is server-owned |
| `media` | id, owner, random private object key, derivative MIME/size/checksum, staged/attached/deleting/deleted state, created/expires_at; no original filename or public URL |
| `processing_attempts` | id, report_id, refresh_request_id, stage, attempt number, pending/running/succeeded/partial/failed/not_applicable, safe reason code, start/end; no raw provider response/error |
| `evidence_versions` | id, case_id, monotonic version, input fingerprint, policy/prompt/model identity, created_at, source references and fragment IDs; logical facts frozen |
| `evidence_fragments` | source and allowed normalized content, observed/retrieved/valid times, retention_policy_version, expires_at, available/expired/redacted/unavailable state |
| `review_events` | id, case_id, actor_user_id, unit_id_at_action, revision, action/time and private outcome; append-only except explicit deletion policy |
| `internal_notes` | id, case_id, author, body, time, expires_at; private model/table; corrections append a superseding note |
| `field_follow_ups` | id, case_id, requested/assigned/completed/cancelled, assigned member, internal outcome, timestamps; evidence/photos use the same privacy rules |
| `reporter_updates` | id, case_id, publisher, safe status, deliberate message, published_at, supersedes_id nullable; separate from notes |
| `jobs` / `idempotency_keys` | durable lease/retry state; owner/operation/key and normalized-request fingerprint UNIQUE |
| `privacy_requests` / deletion ledger | request/actor/scope, suppression and purge state, retries, backup tombstone; no deleted content copies |

Reported coordinates are required finite lat/lng for the minimum intake.
Declared category is one of `SMOKE_OR_BURNING`, `DUST`, `ODOUR`, `OTHER`, `UNSURE`;
it is a resident claim, never a model finding. Capture time can be null; supplied
capture time is explicitly `resident_declared`. Reviewer verification is an
append-only event with method/time, not a replacement of the declaration.
No contact address is required beyond the identity provider account. Submitted
facts cannot be silently edited; withdrawal/deletion are separate operations.

Define separate strict `ResidentReportSummary`, `ResidentReportDetail`,
`AuthorityCaseSummary`, `AuthorityCaseDetail`, and `InternalNoteRead` models.
Never serialize an ORM entity or authority response and strip fields in React.
Resident detail contains only own submitted facts/media availability, receipt,
safe processing state and explicitly published updates. It omits internal notes,
other reporter identity/locations, internal actors, evidence debug inputs, object
keys, private routing reasons and model confidence. Shared summaries use no exact
coordinates. An owner may see their own submitted location; approved reviewers
may see the case location. No anonymous individual-case response exists.

The exact `ResidentReportDetail` allowlist is `id`, `receipt_id`, `accepted_at`,
`description`, `declared_category`, `reported_location {latitude, longitude}`,
`declared_capture_at`, `capture_time_basis`, `media {id, state, expires_at}|null`,
`reporter_status`, `published_updates [{id, status, message, published_at}]`,
`processing {state, safe_reason}`, `withdrawn_at`, and `deletion_state`.
The summary omits description, coordinates and update bodies. No parent ORM
relationship is implicitly serialized. Internal notes are at most 2,000 characters;
reporter messages at most 1,000, deliberately authored/previewed and separately
validated. There is no automatic note-to-update copy operation.

All authenticated HTML, BFF/API JSON, media and exports use `Cache-Control:
private, no-store`; no CDN/Next fetch cache or service-worker persistence.
Logs/analytics allow only request IDs, safe operation/result codes and timings.
No bodies, tokens, identity profiles, exact locations or object paths enter them.

## 6. State separation and legacy mapping

Retain review states `NEW`, `UNDER_REVIEW`, `ACKNOWLEDGED`, `MONITORING`,
`CLOSED_NO_ACTION` and the existing transition matrix. Optimistic revision checks
and a review event are committed atomically. Field follow-up is a separate task,
not proof of action by a government body.

| Existing value | Pilot meaning | Reporter-visible consequence |
|---|---|---|
| `NEW` | Durable case awaiting reviewer | Initial receipt `RECEIVED` only |
| `UNDER_REVIEW` | Internal review started | No automatic publication |
| `ACKNOWLEDGED` | Reviewer has acknowledged internally | No automatic publication or verification claim |
| `MONITORING` | Reviewer will monitor | No automatic publication |
| `CLOSED_NO_ACTION` | Internal closure with reason | Publish `CLOSED` only through explicit reporter update |

Reporter statuses are `RECEIVED`, `IN_REVIEW`, `FOLLOW_UP_PLANNED`,
`UPDATE_AVAILABLE`, `CLOSED`. Only `RECEIVED` is generated automatically at
acceptance. Later status/message publication is a distinct deliberate action
with preview, actor, case scope and expected revision. Corrections append; they
never silently expose a note or erase update history. Privacy deletion may
redact prior text under the explicit retention exception.

Processing stages are `VISUAL`, `ENVIRONMENT`, `CORROBORATION`, `FORECAST`.
Attempt states are `PENDING`, `RUNNING`, `SUCCEEDED`, `PARTIAL`, `FAILED`,
`NOT_APPLICABLE`, `CANCELLED`. Job states are `PENDING`, `RUNNING`, `RETRY_WAIT`,
`SUCCEEDED`, `FAILED`, `CANCELLED`. A field task moves REQUESTED -> ASSIGNED ->
COMPLETED, with cancellation from REQUESTED/ASSIGNED. A reviewer can request or
claim their own task; assigning another reviewer is unit-admin-only. Completion
requires its assignee or unit admin, with an explicit event and revision check.
Processing failure/partial success does not close or delete a case. With no
image, VISUAL is `NOT_APPLICABLE`; do not call Gemini, invent visual fields or
classify the report as `no_visible_pollution`. Add a target-domain text-only
assessment adapter: no visual hypothesis, advisory support `INSUFFICIENT` with
reason `NO_VISUAL_HYPOTHESIS`, and independently available environmental context.
Do not force a nullable image into the existing `StructuredReport` model.

Legacy in-memory records have no authenticated owner or reliable durable custody.
Do not auto-import them into resident accounts or invent a reviewer identity.
Preserve them as synthetic/demo history only. A separately authorized manual
import would require a manifest and explicit ownership; it is outside release.

## 7. PostgreSQL, acceptance, idempotency and worker

Choose PostgreSQL 18, SQLAlchemy 2.1 typed models, psycopg 3, and Alembic 1.x.
Resolve supported stable patch releases and lock dependencies during Phase 1.
Use reviewed Alembic migrations, not production `create_all`. One migration
owner uses a direct connection; API/BFF/worker use bounded pooled TLS connections
and separate least-privilege roles. The documented existing Neon project is a
candidate host, not a currently verified empty database or an authorization to
migrate it. Local tests use a disposable PostgreSQL 18 database, not SQLite as a
substitute for FK, concurrency, locking and transaction tests.

Report acceptance transaction:

1. Verify identity/session, ownership of any staged media, input validity and
   configured admission limits. No AI/provider dependency occurs here.
2. Lock/insert the idempotency record scoped by `(principal, operation, key)`.
   Keys are UUIDs supplied by the client and kept stable across a retry, together
   with timezone-aware `Idempotency-Key-Created-At`. For an unseen key require
   creation within the preceding 24 hours (at most 60 seconds future skew);
   older unseen keys return 410. Compute
   a canonical fingerprint from validated declared fields plus owned media ID.
3. Atomically insert report, its unique case, initial receipt/update, and durable
   `PROCESS_REPORT` job. Consume staged media ownership in the same transaction.
   Store a minimal acceptance response with the idempotency record and commit.
4. Return HTTP 201 with report ID, case-safe receipt, accepted_at, status
   `RECEIVED`, processing `PENDING`, and own detail URL. Do not await the worker.

Same key/body returns the original accepted IDs (HTTP 200 with
`Idempotent-Replayed: true`); same key/different fingerprint returns 409.
Concurrent duplicate requests create exactly one report/case/job through unique
constraints and transaction handling. Rollback leaves none; database failure
returns 503 and never a receipt. Retain idempotency entries while the report
exists, with a minimum 24-hour retry window; deletion redacts request fingerprints
and leaves only a 180-day consumed-key tombstone. Retries against that tombstone
return 410. After tombstone expiry the original request's now-old creation time
still rejects an accidental retry; an explicit new submission uses a new key.
Existing accepted-key lookups can replay throughout report retention, after
ownership and exact fingerprint checks, without reapplying the unseen-key age
check. The key creation header is part of the fingerprint and stable retry
envelope; it is not a claim of the event's capture time.

The `jobs` table is the initial transactional outbox/queue; no redundant broker
or database-to-broker dual write. One logical refresh request has one job, a
unique input/version key and separate stage attempts. Claim due jobs with
`FOR UPDATE SKIP LOCKED`; commit a 120-second lease, heartbeat every 30 seconds,
perform provider IO outside a database transaction, then conditionally finalize
using the lease token. Reject late results from expired/superseded leases.
Recover abandoned leases after restart. At-least-once execution permits repeated
provider calls after crashes; database uniqueness prevents duplicate evidence
versions/publications. Do not claim exactly-once upstream execution.

Three attempts per stage maximum, with 30/120-second backoff for retryable
timeouts/rate limits/transient failures. Honor bounded provider Retry-After;
nonretryable auth/schema/configuration failures become explicit stage failure.
Exhaustion leaves a visible failed/partial processing record and a reviewable
case. Operator/reviewer retry creates a new audited refresh request. Pending
media must still exist and be within retention before each read. Cancellation,
withdrawal and deletion prevent further IO and finalization.
An already in-flight provider request can finish after cancellation; its result
is discarded and no later stage is started. Application deletion cannot undo
processing already accepted by a cloud provider; disclose its separate policy.

Use one Python worker entry point in the API codebase (target
`python -m app.worker`) with the same image and provider adapters. Locally run it
as a separate process/Compose service against local Postgres. Proposed hosted
target is a **separate Render Background Worker** polling PostgreSQL. Existing
`render.yaml` defines only a free web service: no continuous-worker capacity is
assumed. Authorization for a suitable worker plan is an external pilot gate.
If unavailable, keep the worker local and leave hosted processing explicitly
pending. Do not replace durability with FastAPI BackgroundTasks, a Vercel
request lifetime, keep-alive traffic or an undocumented cohosted daemon.

Refresh appends evidence version N+1. Review/publication references an explicit
version; a later result does not silently change an earlier review decision.
Forecast remains a separate outlook after rule evaluation and never enters
corroboration. The initial Google retention policy makes that outlook volatile
only; other permitted fragments use the versioned store. Provider failures
preserve independent source states.

## 8. Private media, retention, deletion and restore

`PrivateMediaStore` exposes put-clean-derivative, read, delete and existence
operations. Select boto3 against a private S3-compatible Cloudflare R2 bucket
for the pilot; credentials/bucket/region approval are external. Disable public
`r2.dev` access and custom public domains. API responses contain application media
IDs, never object URLs/keys. Stream authorized reads through FastAPI and BFF;
no public or presigned browser URL is part of the minimum release.

Local adapter stores files under an ignored private data directory outside
`public/`; tests use a temporary directory and fake S3 client. These are explicit
local/test adapters, not a production filesystem fallback. Render local disk is
ephemeral. Future field images use the same pipeline.

Reuse existing decoding, 16 MP, still JPEG/PNG checks and metadata stripping.
The pilot BFF source upload limit is **4,000,000 bytes**, with at most 64 KiB
multipart overhead. This fits below Vercel's documented 4.5 MB request boundary;
the legacy direct-API 5 MiB limit is unchanged. The narrower pilot limit is an
explicit host adaptation, not a guarantee that every hosting plan accepts 5 MiB.
The client stages an image separately, then submits a report referencing its
ready owned derivative. Persist a media upload intent, write to a random private
key, and mark ready only after successful object storage. Delete orphaned objects
after crash/reconciliation. Never persist the original upload as an object;
close/unlink temporary request spools on success, failure and cancellation.
Do not store original filenames/EXIF. A failed image stage can be retried or
explicitly omitted for text-only submission; no accepted report is contingent
on interpretation success. Bound the cleaned derivative to 4,000,000 bytes too.
Oversized uploads return a clear 413 and offer text submission; exercise the
actual host limit separately in Phase 3. An authenticated private-media response
must also fit its BFF response limit; no general object-download proxy is added.

Proposed pilot defaults below are configurable active-storage ceilings, **not
legal compliance or owner approval**. The earlier deadline wins for reads and
linked content. Backups of permitted content can retain encrypted bytes for up
to seven additional days, explicitly disclosed; Google content and originals
are excluded from persistent backups. Verify host backup scope before collection.

| Content | Default ceiling | Required treatment |
|---|---|---|
| Original image/raw provider response | No application persistence | Request memory/temp spool only; dispose immediately |
| Unattached clean derivative | 1 hour | Delete staging/orphans automatically |
| Attached clean image | 30 days from media creation | Earlier withdrawal/deletion/owner expiry applies |
| Report/case description, exact location, internal notes and updates | 90 days from acceptance | Content purge; no indefinite closure extension |
| Gemini structured interpretation | 30 days from generation | Earlier case/image/privacy deletion applies; no raw response/prompt dump |
| Google current AQ / hourly forecast / current Weather values | No durable persistence; volatile cache at most 15 minutes from retrieval | Published non-EEA ceiling is 1 hour; no database, backup, packet or persistent derived copy |
| FIRMS normalized detections | 30 days from retrieval | Product attribution and source policy metadata |
| Sentinel-5P normalized reductions | 30 days from retrieval | Copernicus attribution, EE/product terms and scientific provenance |
| Minimal security/deletion audit | 180 days | No bodies, direct identity profile or exact coordinates; documented pseudonymous links |
| Encrypted backup / restore window | At most 7 days | Obtain host capability confirmation; replay deletion ledger before any restore is exposed |

Each source requires a versioned retention registry: source/product, consulted
policy URL/date, allowed fields/purpose, acquisition/retrieval times, storage and
export permission, expires_at and attribution. Unknown policy fails closed to
no retained provider content. Record policy review for FIRMS and Earth Engine
delivery terms before real collection; do not infer permission for raw imagery
or portal material from permission for numeric Sentinel data.

Google's current published non-EEA terms permit one-hour caching of current AQ,
hourly forecast and current Weather values. The owner's billing agreement and
permitted-use context still require confirmation. The historic-values exception
does not turn a current observation into indefinitely retainable history.
This plan does not authorize redistribution or assert a new legal conclusion.

The initial pilot deliberately selects `GOOGLE_CONTENT_PERSISTENCE=disabled`.
Neon backup/PITR can capture database rows, so an expiring SQL row alone cannot
guarantee deletion of Google content inside one hour. Do not put those values,
their hashes, or Google-dependent derived rule/support/forecast content in
PostgreSQL, jobs, sessions, backups or exports. An approved reviewer can request
separately labeled live-context through the scoped API; its response is volatile,
no-store and independent of a saved assessment. A 15-minute process cache and
browser expiry timer bound those copies; restart discards them. The read is
audited only as a safe operation/result code, without values or coordinates.

The durable evidence pipeline therefore records these fragments as
`NOT_RETAINED_BY_POLICY` and evaluates its frozen support from the permitted
retained-source inputs only, under explicit input policy
`pilot_retained_sources_v1`. Existing numeric rule thresholds remain unchanged;
Google AQ is unavailable to that saved evaluation. Gemini/FIRMS/Sentinel context
still retains its own limits, and text-only support remains insufficient. The
live Google outlook never upgrades that saved support. Retaining a composite
assessment that used Google requires a later reviewed retention/backup decision;
owner preference alone cannot waive provider restrictions. This intentional
difference from the legacy memory snapshot is visible in API/UI/provenance.

For other permitted fragments, evidence is logically frozen, but retention
overrides continued availability.
Store expiring source content as separately purgeable fragments, with immutable
version headers and explicit redaction events. On expiry, read/export projections
must immediately withhold content, including cached frontend state, even if the
purge worker is behind. Display `EXPIRED_BY_SOURCE_POLICY`/`DELETED` with time and
safe source identity. Physically purge within the configured sweep deadline;
read-time expiry is not itself a substitute for deletion. The source-content
expiry sweep runs at least every minute on an active worker. Stop new retained-
provider collection if the sweeper is unhealthy. Deployment must test physical
deletion, failures and backup expiry before enabling real provider retention.
In the initial pilot, Google content never enters the backed-up fragment store.

Redact all dependent copies, rule input/reason text, summaries and derived
support/forecast values to the earliest restricted-source expiry. Never silently
recompute an old assessment from surviving fragments or retain protected content
in a hash/audit/debug dump. A new assessment requires a new version. UI timers
clear expired fragments and re-fetch the redacted projection. A browser/user
copy cannot be recalled; pilot download/export always omits Google values and
Google-dependent derived assessments pending explicit redistribution permission.

Withdrawal stops new work and removes media availability without claiming the
report was false. A deletion request suppresses access immediately, cancels jobs,
and queues a bounded purge of image, report, evidence, notes, updates, replicas
and caches; delete derivatives within 24 hours or their earlier expiry. Keep
only a minimal deletion ledger needed to prevent resurrection. No reviewer
can restore deleted/expired evidence. Disaster restore is operator-only and
quarantined: apply tombstones and all elapsed TTLs before releasing traffic.
Backups may retain encrypted bytes for their disclosed seven-day window, never
promise immediate physical erasure from backup. Account erasure also requires
the separate identity-provider procedure. No legal-hold system is in this release;
an exception needs a new documented decision before real collection.
Discard all restored authentication sessions and token ciphertext; require fresh
login. Do not resurrect revoked access through an older session backup.

## 9. Legacy interfaces and export compatibility

Phase 0 changes no routes/contracts. During the pilot cutover, preserve the
existing `pollution_event_v1` model/schema/receiver unchanged for isolated
synthetic demos. It requires Gemini evidence and cannot represent text-only
reports or policy-redacted fragments. Use explicitly new `pilot_case_packet_v1`
for v2 manual export, with nullable interpretation and explicit fragment states.
Omit identity/contact, media bytes/URLs/keys and internal notes by default.
Apply source retention/export policy before serialization and hash the exact
allowed exported bytes. State `delivery_mode=MANUAL_EXPORT` or `SIMULATED`,
never government receipt. No import or automatic inter-agency transport.

The current unprotected v1 analyze/corroborate/review/handoff/export and arbitrary
coordinate provider routes cannot remain alternate access paths to real data.
At cutover, `APP_MODE=pilot` returns 404 for all legacy `/api/v1` domain routes.
There is no fallback into the old unauthenticated stores. `/demo` is unavailable
until an isolated synthetic-only demo backend is explicitly configured. Demo
mode must refuse pilot database/private-media configuration and quota-bearing
provider credentials. A public demo uses no pilot database, private
media or live quota-bearing credentials. CORS alone is never the protection.
Retain v1 regression coverage in demo configuration and add explicit pilot-mode
denial tests. No legacy record is silently assigned to a newly logged-in person.

## 10. Configuration and external dependencies

All names here are target settings, not implemented environment parsing.

| Service | Server-only configuration / external requirement |
|---|---|
| Next.js BFF | `APP_BASE_URL`, `BACKEND_API_BASE_URL`, `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`, `AUTH0_SECRET`, `AUTH0_AUDIENCE`, `SESSION_DATABASE_URL`, `SESSION_ENCRYPTION_KEY`; exact HTTPS callback/logout origins |
| FastAPI | `DATABASE_URL`, exact `AUTH0_ISSUER`, `AUTH0_AUDIENCE`, `AUTH0_ALLOWED_CLIENT_ID`, `PILOT_TRIAGE_UNIT_ID`, admission/retention settings; no shared fake identity |
| Migrations | `MIGRATION_DATABASE_URL` direct TLS connection, separate migration role and explicit target acknowledgement |
| Worker | Bounded DB role, same provider configuration and private-media access; approved Render worker service |
| Private storage | `MEDIA_BACKEND=s3`, `S3_ENDPOINT_URL`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`; bucket private, lifecycle/region confirmed |
| Providers | Existing backend Google/FIRMS keys and backend Google identity; new storage/export policy registry and product-specific gates |
| Browser | Only separate restricted Maps browser key/map ID as needed; no API token, DB/storage secret, backend provider key or user-role configuration |

Initial pilot admission defaults: at most 10 accepted reports per resident per
day, 10 staged image uploads per hour, 2 evidence refreshes per case per hour,
one provider-processing stage per case at a time, and a configurable global
provider budget. Use database-backed limits; log no image/location in rejections.
Owner approves budgets for real collection. Over-budget processing remains
pending/visible; an already accepted report is never deleted for quota failure.

Local deterministic development needs no paid cloud account: disposable local
PostgreSQL, temporary filesystem media/fake S3, fake providers, explicit test
principals and signed fixture JWKS. Production must refuse test adapters.
Managed OIDC callback/refresh/logout, private R2 access, actual Neon schema and
worker deployment are separate live checks; fixtures never count as those checks.

Freeze target retention setting names/defaults: `REPORT_CONTENT_TTL_DAYS=90`,
`MEDIA_DERIVATIVE_TTL_DAYS=30`, `MEDIA_STAGING_TTL_SECONDS=3600`,
`GEMINI_CONTENT_TTL_DAYS=30`, `FIRMS_CONTENT_TTL_DAYS=30`,
`SENTINEL_CONTENT_TTL_DAYS=30`, `MINIMAL_AUDIT_TTL_DAYS=180`,
`BACKUP_RETENTION_DAYS=7`, `GOOGLE_CONTENT_PERSISTENCE=disabled`,
`GOOGLE_VOLATILE_CACHE_TTL_SECONDS=900`, `PILOT_UPLOAD_MAX_BYTES=4000000`.
Validate positive bounded values; the Google cache cannot exceed 900 seconds
under this contract and no enabled durable-Google mode exists. Backup setting
is an asserted host capability to verify, not a switch that configures Neon.
Provider policy caps override operator-entered values. Changes to these defaults
before real collection require an owner decision recorded in DECISIONS.

Before real-data collection the owner must approve retention/backup windows,
media/identity processing regions, notices and provider permitted use/export,
unit operator/triage roster, budgets and worker plan. These are external release
gates; they do not prevent local implementation of the contract.

## 11. Sequenced phases and concrete completion gates

No phase below is implemented or complete unless PHASE_STATUS records its actual
outputs. No detailed Phase 1–7 prompts were supplied with Phase 0; this dependency
map is the narrow inferred sequence. Reconcile a later supplied phase prompt
explicitly before changing this contract. Every phase updates status/report,
preserves the rejected research, runs relevant existing regression checks, and
regenerates API/types/schema when affected.

| Phase | Deliverable | Required local completion evidence |
|---|---|---|
| 0: Baseline and contract | These four documents, current source/test record | Fresh baseline, choice rationale, access/retention/worker contract, consistent local links; no runtime edits |
| 1: Persistence foundation | SQLAlchemy/Alembic models and repositories, disposable PG setup | Fresh DB upgrade, constraints/one-case uniqueness, transaction rollback and restart persistence, scoped repository queries, lease/idempotency concurrency on PostgreSQL, migration rehearsal without production access |
| 2: Identity and authorization | Auth0 BFF sessions, API verification, approved memberships | Signed JWT bad type/signature/issuer/audience/expiry/client tests, key rotation, logout/revoked session, two residents/two units isolation for every read/write/export/media path, CSRF, missing-config fail-closed; managed login live check separately pending if credentials absent |
| 3: Durable resident intake and private media | `/resident` routes, text-only acceptance, staged derivative storage | AI/provider outage still returns durable receipt, parallel retries one report/case/job, changed body 409, own-list/privacy, EXIF removal/spool cleanup/orphan cleanup, unauthorized media denied, hosted upload boundary tested; real storage check distinct |
| 4: Durable processing and evidence | PG worker, stage attempts, immutable versions, policy fragments | Crash/restart/lease fencing, bounded retries, partial failure/text-only N/A, refresh appends, forecast isolation, provider-derived copy redaction at expiry, physical deletion and sweeper-failure tests, synthetic source-policy fixtures; paid worker/live sources separately gated |
| 5: Reviewer workflow | Unit queue, notes, field follow-up, deliberate reporter updates | Revision conflicts, exact state mapping, no auto-publication, notes never in resident JSON/cache/error, unit-admin non-escalation, revocation during actions, no dispatch claim |
| 6: Pilot release hardening | Privacy deletion/restore, scoped manual export, operational runbooks | Deletion across all copies and backups restored under quarantine, auth/session/admission checks, source-safe new packet plus unchanged v1 demo contract, restart/outage/backpressure drills, owner gate record; deployment only separately authorized |
| 7: Comprehensive UI polish | Refine completed resident/authority flows using real preceding output | Keyboard and narrow-screen journeys, all loading/partial/error/expiry states, accessibility/overflow, unchanged privacy/science/authorization assertions; no speculative data |

Minimum end-to-end release gate: resident A signs in, submits text with providers
offline, receives a durable receipt, retries safely and survives API/worker
restart. Resident B cannot list/read A's report or media. Approved unit A reviewer
sees its case; unit B does not. A private note stays private, while an explicit
published update appears to resident A. Optional image/analysis and a later
refresh preserve unknown capture time and prior version references. Revoking
membership/session blocks the next action. Source expiry redacts all copies;
deletion and backup restore do not resurrect content. Manual/simulated export
stays clearly labeled. Only then consider a real-data pilot, with external
authorization and live checks recorded separately.

## 12. Primary references reviewed in Phase 0

Reviewed 10 November 2026; implementation phases must check pinned-version docs
again when adding dependencies. The choices above are application decisions,
not a claim that the integrations have been exercised live.

- [Auth0 official Next.js SDK](https://github.com/auth0/nextjs-auth0) and
  [database session / hook / logout examples](https://github.com/auth0/nextjs-auth0/blob/main/EXAMPLES.md).
- [SDK option to disable browser access-token endpoint](https://github.com/auth0/nextjs-auth0/blob/main/src/server/client.ts).
- [Auth0 access-token profiles](https://auth0.com/docs/secure/tokens/access-tokens/access-token-profiles),
  [RFC 9068](https://www.rfc-editor.org/rfc/rfc9068.html), and
  [PyJWT verification](https://pyjwt.readthedocs.io/en/stable/usage.html).
- [SQLAlchemy 2.1](https://docs.sqlalchemy.org/en/21/intro.html),
  [Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html),
  [psycopg 3](https://www.psycopg.org/psycopg3/docs/),
  [node-postgres pooling](https://node-postgres.com/features/pooling),
  [Neon SQLAlchemy connection guidance](https://neon.com/docs/guides/sqlalchemy),
  [PostgreSQL queue locking](https://www.postgresql.org/docs/18/sql-select.html#SQL-FOR-UPDATE-SHARE).
- [Render worker model](https://render.com/docs/background-workers) and
  [free service restrictions](https://render.com/docs/free).
- [R2 S3 API compatibility](https://developers.cloudflare.com/r2/api/s3/api/) and
  [public bucket controls](https://developers.cloudflare.com/r2/buckets/public-buckets/).
- [Vercel request/response limits](https://vercel.com/docs/functions/limitations).
- [Google source-specific terms, sections 2 and 21](https://cloud.google.com/maps-platform/terms/maps-service-terms),
  [AQ policies](https://developers.google.com/maps/documentation/air-quality/policies),
  [Weather policies](https://developers.google.com/maps/documentation/weather/policies).
- [NASA data license guidance](https://science.data.nasa.gov/about/license),
  [Copernicus Sentinel data terms](https://dataspace.copernicus.eu/terms-and-conditions),
  [Vertex data governance](https://cloud.google.com/vertex-ai/generative-ai/docs/data-governance).

Phase 0 stops here. No migration, managed tenant, bucket, worker, new route or UI
has been created by this document.
