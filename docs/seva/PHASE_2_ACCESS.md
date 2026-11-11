# Phase 2 — identity and access isolation

Date: 10 November 2026 (Asia/Calcutta). Contract: `seva_pilot_v1`.
Status: **COMPLETE_LOCALLY_VERIFIED**. Live managed identity/hosted release gates remain pending.
Source HEAD/base: `6f071afd10f0ffed024448ac87d3bfae9ec8abc4`.
Local branch: `codex/seva-phase-2`. Phase 0–2 work remains uncommitted.
The selected checkout and unrelated presentation/output artifacts are preserved.
No push, deployment, paid provisioning, production migration, invitation email,
provider quota call or real-user enrolment occurred.

## Implemented identity boundary

The official Auth0 Next.js SDK **4.33.0** handles Authorization Code/PKCE, state,
nonce, signed ID-token verification, managed refresh and back-channel logout.
The application uses its database-session interface, including the atomic `update`
method required to prevent logout/rolling-session resurrection. Installed source
and versioned official examples were inspected before integration.

The browser receives a host-only `__Host-airshedos` session cookie, Secure,
HttpOnly, SameSite=Lax, Path=/, carrying an encrypted opaque SDK session ID.
Access/refresh tokens and the random backend session binding stay server-side.
The SDK token/profile/connect routes are blocked; account linking, role selection,
password authentication code and production test-login routes are absent.

The custom `pg` session store commits identity lookup, session metadata and sealed
SDK data transactionally. Identity is the exact verified `(issuer, subject)` pair;
email/profile names never create a link or authority grant. A disabled identity is
not reactivated by login. New session creation needs a single-use, short-lived
server permit created only in the SDK's successful validated callback. Ordinary
rolling/refresh updates require an existing active, unexpired record and cannot
insert a missing session, clear revocation or extend its absolute ceiling.

Tokens are sealed with maintained `jose` Compact JWE (`dir`/`A256GCM`) using a
separate 32-byte server key. An optional previous key supports rotation. Cookie
and encryption secrets must differ. Python's session metadata table has no token
ciphertext column: encrypted data lives in `auth_session_secrets`, with separate
database grants. Defaults are eight-hour absolute and 30-minute idle sessions.
Expired/revoked encrypted data is purgeable; consumed session IDs remain tombstoned
through the maximum token/refresh window. Restores must discard sessions entirely.

FastAPI independently verifies custom-API access tokens with **PyJWT 2.15.1**:
RS256 only, access-token `typ=at+jwt` (or its RFC media spelling), fixed issuer,
`urn:airshedos:pilot-api` audience, allowed BFF client, required subject/issued-at/
expiry/jti/client claims, `access:airshedos` scope and at most ten-minute token
lifetime. Clock skew is bounded to 60 seconds. ID tokens, wrong signatures,
algorithms, issuers, audiences, clients, missing claims and expired tokens fail.
JWKS comes from a fixed configured HTTPS issuer, with bounded fetch size/timeout,
five-minute caching and rate-limited unknown-key refresh; JWT headers cannot choose
URLs or keys. A token is insufficient without the matching active PostgreSQL app
session, issuer/subject binding and active local account.

The dependency constructs an internal principal only after both checks. The
repository rechecks current account/session state inside each operation, including
mutations under locks. Membership comes from SQL, never cached role claims.
Revocation is effective on the next action; writes already holding authorization
locks may finish before revocation commits. Session expiry is rechecked after lock
waits. Runtime database queries have bounded lock/statement timeouts.

## BFF, logout and route shells

`/api/app/v2/...` forwards only explicitly allowlisted methods/paths/query fields.
It constructs Authorization/session headers from the server session and forwards
no browser Authorization, Cookie, user, role, unit or proxy identity headers.
There is no client-chosen upstream URL. JSON mutations are bounded to 8 KiB and
require exact Origin, acceptable Fetch Metadata and a timing-safe comparison with
the session-bound CSRF nonce from `/api/app/csrf`. Media/JSON responses and protected
HTML/errors use private/no-store caching; no access token goes into localStorage,
React props, client components or a profile endpoint.

Only `/resident` and `/authority` are accepted login destinations in this phase.
External, encoded, backslash and arbitrary callback destinations cannot become a
return URL. The login proxy strips other caller-supplied authorization parameters.
`/resident`, `/authority` and `/sign-in` provide restrained functional shells with
clear unavailable/unauthenticated/no-unit states, labelled navigation and logout.
They do not build the report form or reviewer dashboard. Browser checks include
390 px width and keyboard navigation. Authentication guards assist navigation;
the backend independently enforces every protected operation.

Logout is POST-only through the CSRF-protected BFF. It revokes the local binding
and removes sealed tokens **before** provider logout/discovery. CSRF and logout
paths do not attempt access-token refresh first, so an expired token plus provider
outage cannot prevent local logout. Provider logout is best effort after durable
local revocation; failure returns a safe local signed-out destination. Database
revocation failure returns an error and does not falsely claim success. The SDK
validates back-channel logout tokens before issuer-scoped subject/SID revocation.
Upstream-only suspension is not promised immediate without a functioning tenant
back-channel integration; operator local disablement is the emergency control.

## Ownership, units and controlled provisioning

Resident SQL predicates restrict lists/counts and detail/media reads to the current
owner before pagination. Authority predicates require active approved membership
in the assigned approved, non-prototype unit. Requested unit IDs select a scope;
they do not grant it. Case reads/actions, queue/search/state counts, map points,
media and exports each check independently. Cross-unit IDs cannot leak counts or
locations. Unit members can never use the resident endpoint to read someone else's
submission. The resident DTO allowlist omits notes, internal actors, identity,
object keys and authority evidence/debug data; reviewer DTOs are separate.

Response policy: anonymous/invalid token/session requests return 401; missing or
out-of-scope objects/units return the same 404. Unsupported identity fields return
generic 422 without echoing bodies. Stale revisions return 409; admission limits
429; unavailable configuration/database/private storage 503. An account/session
revoked between initial authentication and a transaction can return generic 403;
it still discloses no object. Validated but illegal review transitions return 422.
Protected access logs redact IDs and query strings; no bodies/tokens are logged.

Unit admins can list own-unit membership references, propose a reviewer invitation
for an already verified identity and suspend another own-unit reviewer. A proposal
is pending, expires after seven days and grants nothing. There is no emailed invite
or email/domain matching. Admins cannot propose an admin role through this API,
approve grants, suspend another admin, operate in another unit or grant themselves.
Operator approval/reactivation is a separate audited management action.

`python -m app.access.provision` provides the offline operator console. Its caller
must authenticate as the separately configured PostgreSQL management login and
match `SEVA_OPERATOR_DATABASE_ROLE`; API/BFF credentials are not that authority.
First bootstrap additionally requires the exact configured initial operator subject,
an existing active verified identity and an empty operator-grant registry. Subsequent
unit/initial-admin bootstrap, proposal approval and account disablement require an
active operator grant. Targets use the fixed configured issuer and exact existing
subject. Management credentials are the offline trust root; this is not an HTTP
body/user-ID authorization mechanism. Operator status alone confers no case read.
Account disablement revokes memberships/sessions and removes sealed session data.
No public operator bootstrap/grant endpoint exists and no real operator was enrolled.

## Database, export and abuse controls

Migration `seva_0002` adds the session separation, operator/proposal/access-audit
records and shared quota/admission tables: **24 tables total** including Phase 1.
Phase 1 placeholder sessions are invalidated rather than reinterpreted as verified
SDK sessions. Three inert `lock_guard` columns permit PostgreSQL row locks without
granting API/session roles the ability to alter account status, unit approval or
session revocation/expiry. They are not permission claims.

`apps/api/scripts/pilot_roles.sql` is an explicit operator-applied grant template.
The API can read session metadata and perform domain actions, but cannot read token
ciphertext or change membership roles. The session role can create minimal identities
and maintain sealed sessions, but cannot read cases, grant authority or reactivate
accounts. A separate management role owns migrations/provisioning; cleanup needs its
own reviewed permissions. Real restricted-role tests exercise authorized API actions
as well as denied ciphertext, grant, case and active-account operations. This does
not claim hosted roles have been configured or that row-level security is installed.

The new `pilot_case_packet_v1` endpoint is deliberately metadata-only, manual export.
It contains case/review/version references, no report identity, description, exact
location, notes, media keys/bytes/URLs, provider payloads or content hashes. It claims
no official dispatch or receipt. Wider payload export remains subject to later source
policy review. Legacy `pollution_event_v1` remains byte-identical.

Shared PostgreSQL admission defaults, configurable as pilot policy rather than
measured capacity:

| Setting | Default |
|---|---:|
| `SEVA_REPORTS_PER_DAY` | 10 per resident |
| `SEVA_UPLOADS_PER_HOUR` | 10 per resident |
| `SEVA_REFRESHES_PER_HOUR` | 2 per case |
| `SEVA_PROVIDER_CALLS_PER_DAY` | 100 globally |

Atomic UPSERT counters use the database UTC clock, scoped to verified local user,
case or fixed global budget. They are transactionally integrated with intake,
staging and refresh. Idempotency replay does not charge intake again. Paid-analysis
reservation is an internal future-worker seam, with one bounded active admission
per case; it executes no provider call. Budget exhaustion never removes an accepted
report/job. Expired counters/admissions are sweepable. Proxy/IP headers do not define
identity or quota scope; no trust in arbitrary X-Forwarded-For is introduced.
There is no distributed unauthenticated IP limiter or claim of measured capacity.

## Prototype/pilot boundary and scope

`APP_MODE=prototype` preserves the existing demonstration and its v1 regressions.
It does not implicitly attach the resident database or authenticate old demo records.
`APP_MODE=pilot` on FastAPI blocks **every** legacy `/api/v1` route, including quota-
bearing providers and exports, and uses database/schema-aware readiness. Missing
pilot identity configuration fails closed rather than falling back to demo data.
The frontend's pilot root offers resident/authority entry links. The old client
command-center source was moved byte-identically into a prototype component.
Set pilot mode explicitly on both services before any real collection; this phase
did not change the existing hosted service's mode or credentials.

Resident submission UI/HTTP intake, hosted private uploads, complete reviewer
workflows, analysis worker, notifications and redesign are not implemented here.
Protected reads/actions consume Phase 1 seams for access verification. Provider
retention remains off by default; forecast rules and `MODEL_NOT_ACCEPTED` are unchanged.

## Configuration and local reproduction

New server settings are documented in root/backend and `apps/web/.env.example`.
For local Next.js use its own ignored `.env.local`; the root provider-secret file
is not copied or automatically loaded into the frontend. All secrets remain without
`NEXT_PUBLIC_`. Exact HTTPS origins and canonical issuer are mandatory for hosting;
local HTTP requires explicit localhost/development permission and is rejected in
production. Nonlocal database connections require verified TLS. No app startup
performs migrations or provisions roles.

Required managed setup: Auth0 Regular Web Application, exact `/auth/callback` and
logout origins, custom API audience `urn:airshedos:pilot-api`, RFC 9068 RS256 access
tokens with `access:airshedos` and lifetime at most 600 seconds, refresh rotation and
applicable back-channel logout settings. Verify tenant/browser login, refresh,
logout and revocation before release. Auth0/session/database settings were absent
from both process configuration and root `.env` key presence checks this session;
no values were printed and no live managed sign-in rehearsal is claimed.

With the disposable PostgreSQL setup from [Phase 1](PHASE_1_PERSISTENCE.md):

```sh
cd apps/api
export TEST_DATABASE_URL='postgresql+psycopg://seva_test:synthetic_local_only@127.0.0.1:55432/seva_phase1_test'
export SEVA_MIGRATION_DATABASE_URL="$TEST_DATABASE_URL"
.venv/bin/alembic upgrade head
.venv/bin/alembic check
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
cd ../web
TEST_DATABASE_URL="$TEST_DATABASE_URL" npm run test:identity
npm run generate:api
npm run lint
npm run typecheck
npm run build
```

Test fixtures refuse a nonlocal/unexpected database and exercise clean migration
to head. SDK tests validate signed synthetic OIDC responses with the actual SDK,
encrypted PG store and a loopback FastAPI process receiving a real signed fixture
access token through the actual BFF function. Fixtures are not production login
routes and no environment variable selects fake identity in runtime `app/` code.
CI now runs these Node/Python integration checks with PostgreSQL and a test Python
path. Remote CI is not claimed because nothing was pushed.

For an operator-approved host, create separate database roles securely, review and
apply `pilot_roles.sql` with psql identifier variables, then use the console with
`SEVA_OPERATOR_DATABASE_URL`, `SEVA_OPERATOR_DATABASE_ROLE`, `AUTH0_ISSUER` and the
one-time `SEVA_INITIAL_OPERATOR_SUBJECT`. Provisioning is an explicit management
operation, never part of ordinary login. No hosted console action was run here.

## Verification and remaining gates

All required local gates passed using synthetic fixtures and a dedicated disposable
PostgreSQL 18 container, not SQLite or a hosted database:

| Gate | Executed result |
|---|---|
| Clean database/current schema | Guarded test DB downgraded to empty, upgraded through both migrations to `seva_0002`, model drift/table/FK checks PASS |
| Two residents/two units | Own/other reports; anonymous list/detail; citizen denial of officer/admin actions; cross-unit counts, search, map, action, media and export checks PASS |
| Provisioning/revocation | Pending proposal grants nothing, no admin-role escalation or cross-unit admin action, controlled bootstrap/approval, same old token denied immediately after suspension: PASS |
| Token/session boundaries | Bad signature/algorithm/type/issuer/audience/client/scope/claims/lifetime, expired/revoked sessions, wrong binding/subject and disabled account: PASS |
| Real database privileges | Authorized API action under restricted role works; ciphertext/role changes denied; session role denied case data/account reactivation: PASS |
| Shared admission | Real separate Python processes contend against the same PG counter: one acceptance/one rejection at the limit. Replay is free; paid budget does not remove accepted intake: PASS |
| Actual SDK and cross-language flow | Signed synthetic OIDC/PKCE/state/nonce → encrypted PG session → actual BFF function → loopback FastAPI signed access-token/session validation: PASS |
| Logout and persistence races | Two stores share state, concurrent logout/update cannot recreate a session, back-channel logout invalidates access, expired-token/provider-outage local logout succeeds: PASS |
| Functional browser shells | Missing configuration, anonymous BFF/blocked token/profile routes, safe return navigation, mobile/keyboard paths plus all existing workflows: PASS |

Final commands/results:

- API `TEST_DATABASE_URL=... .venv/bin/python -m pytest -q`: **592 passed**, two
  existing dependency deprecation warnings, 47.80 seconds; no skipped PostgreSQL
  evidence. All 561 prior tests remain, plus 28 access and three scanner cases.
- API Ruff check and format: PASS, 115 Python files.
- Web `TEST_DATABASE_URL=... npm run test:identity`: **5 passed**, zero skips,
  approximately 3.1 seconds in the final run. The intentionally injected provider
  outage emits an expected SDK diagnostic; it contains no real user/token data.
- Web lint/typecheck and Next.js 16.4.6 production build: PASS.
- Web `npm run test:e2e`: **62 passed**, 1.7 minutes, final production standalone
  build with provider-disabled local API; all 58 original browser journeys retained.
- Separate production pilot-root HTTP smoke on loopback: PASS; workspace entry
  replaces the prototype. Test servers were local only.
- OpenAPI exporter/frontend generation: PASS; v2 schema/types deliberately updated.
  Four unchanged receiver/scientific/protected-record fingerprints matched HEAD;
  moved prototype UI source matched its original bytes exactly.
- Secret scan including compiled artifacts: PASS, **2,580 files, zero findings**.
  Initial PEM-header-only false positives from maintained parser code were resolved
  by detecting actual encoded key material, including JS/JSON newline escapes;
  scanner regression tests passed. No directory or package was exempted.
- Git whitespace and all six phase documents/local links: PASS.

Temporary API/web/pilot-root servers and the dedicated synthetic PG container are
stopped/removed at handoff. No existing container or live data was changed. Local
completion does not claim remote CI, real tenant login or a deployed durable pilot.

Dependency choices were checked against the official
[SDK v4.33.0 examples](https://raw.githubusercontent.com/auth0/nextjs-auth0/v4.33.0/EXAMPLES.md),
[Auth0 token profiles](https://auth0.com/docs/secure/tokens/access-tokens/access-token-profiles),
[PyJWT usage](https://pyjwt.readthedocs.io/en/stable/usage.html) and
[node-postgres transactions](https://node-postgres.com/features/transactions).
Added pg 8.23.1, jose 6.2.17, @types/pg 8.23.1 and test-only tsx 4.23.15.
Next.js and matching lint configuration were updated from 16.3.4 to 16.4.6 as a
targeted prerequisite after published Next security advisories, including
[GHSA-673q-mjm6-r5xr](https://github.com/vercel/next.js/security/advisories/GHSA-673q-mjm6-r5xr).
No broad automatic dependency upgrade was performed.

Runtime npm audit still reports one existing high-severity `source-map-js` 1.2.1
advisory about untrusted indexed source-map offsets
([advisory](https://github.com/advisories/GHSA-68fv-2mgg-jv7q)); the application adds
no source-map ingestion endpoint. The last install also reported existing development
toolchain advisories. They remain release-hardening work, not a zero-vulnerability
certification or an ignored passing audit. Auth0/pg/jose/PyJWT are not identified by
this runtime audit. None of this substitutes for hosted privacy/security review.

External gates: real Auth0 login/refresh/back-channel rehearsal; separately approved
Neon roles/migrations/backup window; hosted private R2 adapter; notices/retention,
unit roster and budget approval; scheduled cleanup/monitoring; later worker and
release authorization. Next phase: authenticated resident intake and private uploads,
consuming these verified identity/ownership/admission seams.
