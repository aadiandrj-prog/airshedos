# Deployment and GitHub publication

11 November 2026. User authorised GitHub publication and checking Render, Vercel and Neon.
The user is operating the hosting dashboards in Helium; automated Helium access was not
approved. No credential value is requested in chat or stored in this record.

## Source and current public services

Implementation commit: `2121566` on `codex/seva-phase-7`, preserving base `6f071af`.
Production merge: `a5ead73ec2dc8bdaf751a20e7ab618dd4fcbd58b`, [PR #15](https://github.com/aadiandrj-prog/airshedos/pull/15).
Its source head 05e08af passed all checks on both push and merge-preview runs:
[push checks](https://github.com/aadiandrj-prog/airshedos/actions/runs/43017330931),
[merge-preview checks](https://github.com/aadiandrj-prog/airshedos/actions/runs/43017342471).
Vercel reported successful Production deployment for the merge. The clean domain now serves
the new homepage and configured sign-in; the login redirect has the exact production
Auth0 callback and API audience. Anonymous BFF/me and pilot report-list reads return 401.
The owner confirmed successful preview login after correcting SESSION_DATABASE_URL scope.
Production login completion and full case journeys are not claimed by these public probes.

The old Render service's Auto-Deploy is off (owner confirmed); the separate pilot API stays
in service. Fourteen obsolete fully merged remote branches were removed, retaining main
and codex/seva-phase-7 for active preview/API dependencies. Git history was preserved.
No .tech domain is registered yet; no registrar/DNS or paid-service action occurred.

## Environmental overview follow-up

Source 934d86a merged through PR #16 as 994d0d1 after all source-head and merge-preview
checks passed. /explore adds public fixed-area context using existing providers and design,
shared PostgreSQL admission and volatile expiry. See [implementation and verification](ENVIRONMENT_OVERVIEW.md).
Original-host Google AQ/weather/forecast and NASA FIRMS were live-checked successfully.
The new pilot host still reports those provider credentials unavailable. The owner reports
Render dashboard maintenance; adding its five private overview settings and changing its
branch to main remains pending. No new service/migration/auth configuration is required.
Do not claim new-host live readings until the post-configuration bounded check succeeds.
Vercel Production succeeded for 994d0d1; public /, /explore, /privacy and /terms independently
returned 200 with expected content. Anonymous private account access remained 401/no-store.
The public same-origin proxy returns the old pilot API's honest 404/no-store until its
new code/settings are deployed. The published interface is distinct from activated sources.

## Final location and design release

[PR #17](https://github.com/aadiandrj-prog/airshedos/pull/17) merged as 99c6ed3 after all
exact-head and merge-preview jobs passed: 684 backend, 8 identity/proxy, 16 public/resident/
reviewer browser journeys in development and production HTTPS, 62 legacy browser tests,
frontend/contracts/Ruff/secrets. CI package-mirror DNS failures were repaired without
removing checks; signed Ubuntu packages now use bounded reachable-mirror selection.

Vercel Production succeeded; Render serves the new optional location contract. An isolated
production browser run verified zero automatic source calls, one explicit synthetic-device
Gurugram lookup rounded before transmission, live Google AQ/weather/forecast and NASA FIRMS,
chart/clear behaviour, methodology and private-account 401. The measured lookup was 5,217ms,
N=1; no capacity or accuracy inference. No real device location, live provider payload or
live-result screenshot was persisted. No new service/setting/migration/auth setup required.
The public experience is at [the clean home](https://airshedos.vercel.app/) and
[explorer](https://airshedos.vercel.app/explore). Private reviewer/worker/cleanup/media
readiness is separate. See [full evidence](FINAL_EXPERIENCE.md).

## Earlier publication and probe history

Published application foundation: `6d95f5db0336c614a9cae4e8d014138472e734cb`.
Remote [GitHub checks](https://github.com/aadiandrj-prog/airshedos/actions/runs/42993136042) completed successfully:
backend (including actual PostgreSQL and signed resident/reviewer journeys), legacy browser,
frontend and secret jobs all passed for `6d95f5d`. Earlier e86abac/5198f0f runs also passed.
Unrelated decks/build/output artifacts and actual secret files are excluded from the commit.
The original supplied design files are retained byte-for-byte. Two original reference
files contain whitespace; narrowly scoped .gitattributes exclusions preserve those originals.
One extra gateway EOF blank line was removed; no runtime behavior changed.

Read-only HTTPS checks in this session:

| Service | Observed result |
|---|---|
| [Vercel public site](https://airshedos.vercel.app) | HTTP 200, 0.78 seconds; existing prototype |
| [Render liveness](https://airshedos-api.onrender.com/health) | HTTP 200, 22.45 seconds including startup; status ok |
| [Render readiness](https://airshedos-api.onrender.com/ready) | HTTP 200, 0.37 seconds; storage=in_memory, data_mode=demo |
| Neon | Owner-approved initialisation completed: independently verified seva_0006, 31 tables, empty domain records, QUARANTINED |

No paid provider, real report, end-user authentication or private-media call was made by these probes.
A green old-prototype /ready does not verify the new pilot or its database connection.

The preview deployment URL is [airshedos-agrlq8s4u-grease-liquor.vercel.app](https://airshedos-agrlq8s4u-grease-liquor.vercel.app).
Anonymous HTTP requests redirect to Vercel sign-in; the resulting HTTP 200 is the login page,
not an independently verified app render. The attempted anonymous asset probe therefore
does not establish that deployed app bundles were inspected. No remote asset-scan pass
is claimed; the local final build/secret gates and remote secret job passed.

The user confirmed Vercel root `apps/web`, Render branch `main` and root `apps/api`.
Vercel production tracks `main`. The user added APP_MODE on Production and Preview, then
corrected its value from `PILOT` to exact lowercase `pilot`, redeployed the phase-7 preview,
and confirmed the new “A clearer way to report local pollution” homepage. This user-observed
render is distinct from the anonymous probe blocked by Vercel protection. Hosted login,
report intake and review have not passed an end-to-end check.

The user corrected the Neon observation: the database branch is `production`; `primary`
is an archived compute, not that branch. The production compute says “Compute is suspended
and automatically activates on client connections”, which is normal auto-suspension.
No unarchive/restore operation was indicated. The owner then supplied the exact direct
endpoint, neondb/neondb_owner and a read-only result (PG 18.6, zero user relations).
They explicitly approved schema initialisation; its actual execution is recorded below.
Backup/retention capabilities remain to verify before real collection.

The user created the Auth0 regular web application and supplied its public domain/client
identifier. They confirmed callback URLs, API identifier/RFC9068 profile, access:airshedos
permission, app user-delegated grant and refresh rotation were saved. These are owner-reported
dashboard settings; live sign-in/server binding is still pending. The
stable branch alias is [the phase-7 preview](https://airshedos-git-codex-seva-phase-7-grease-liquor.vercel.app/);
the individual deployment URL changes on rebuild and is not the chosen callback origin.
No Render background worker or cron job was found. Render's APP_MODE was previously set
to uppercase `PILOT`; correction to `prototype` while the old main is in service was advised
but not confirmed. New API code only accepts lowercase `prototype` or `pilot`.

## Why production is not switched yet

The new pilot requires managed identity, database roles/schema, an external recovery epoch,
a staffed approved triage unit, a continuous durable worker and cleanup. Private media must
be configured or text-only explicitly selected. Existing root render.yaml targets the old
prototype and retains live-provider settings; the new isolated prototype deliberately refuses
those credentials. Blindly deploying that configuration would fail startup. A Neon project
alone does not establish application persistence or permissions.

Publish/review the implementation and remote checks before a production branch change.
Use the [private-pilot runbook](PILOT_RUNBOOK.md) and [environment template](pilot.env.example).
Do not copy database administrator credentials into both services, expose a database URL
through NEXT_PUBLIC variables, run local test tools on Neon, or create a fake production login.
The explicitly approved initial Neon migration has now completed. No billable worker or
new paid service has been provisioned here.
The [reviewable Render service plan](RENDER_PILOT_PLAN.md) describes roles, commands and
estimated base charges. The user selected **keep preview only for now**; do not create paid
services. This leaves continuous hosted worker/cleanup readiness pending, with no bypass.

## Deployment-prerequisite follow-up

Added `python -m app.persistence.migrate`, an offline operator command with explicit exact
host/database/login and expected revision acknowledgement. Hosted targets require a direct
connection and verified TLS/CA. The command rejects connection overrides, nonempty initial
targets, revision mismatch and concurrent migrations; all DDL/checks share a transaction.
Ordinary Alembic retains its loopback guard. This prepares a reviewable hosted workflow;
it has now been run on the approved Neon target. See the [actual migration record](NEON_SCHEMA_CHANGE.md).

Added a separate restricted cleanup-role grant script. Actual PostgreSQL coverage verifies
content/media and eventual tombstone purge without token ciphertext reads, membership grants,
recovery release writes or worker-heartbeat writes. Runtime configuration must use restricted
roles rather than owner credentials; no hosted runtime-role binding is verified yet.

Local follow-up checks: `TEST_DATABASE_URL=<guarded loopback synthetic target>
SEVA_TEST_PG_CONTAINER=airshedos-deploy-pg .venv/bin/pytest -q`: **657 passed**, 51.91s,
two existing FastAPI/Starlette deprecation warnings. Includes 14 checked-migration tests
(actual PostgreSQL atomic rollback, operator concurrency, exact revision and empty-target
guards) and restricted cleanup-role purge/denial coverage. Ruff lint/format: PASS, 148 files.
Signed SDK/session/BFF/Python identity: **5 passed**, zero skips, 2.99s; the deliberately
injected identity-provider outage failed closed. Generated OpenAPI/receiver contracts are
unchanged. Secret scan: PASS, zero findings; git diff --check: PASS. No remote DB query or
paid call was part of these local checks.

Hosted migration verification (11 November, 15:34 IST): full verified TLS with installed
Certifi CA bundle after the system-chain lookup failed before DDL; exact target/login,
empty catalog checked; transaction committed; fresh connection read back seva_0006 and
all 31 expected tables, zero domain records, recovery QUARANTINED with NULL epoch.
No release, runtime-role grants or worker activation was performed. Next dependency is
separate restricted runtime credentials/recovery binding before configuring hosted login.

Subsequent runtime preparation: created dedicated airshedos_api, airshedos_session,
airshedos_worker and airshedos_cleanup LOGIN/NOINHERIT accounts, with no elevated flags or
role memberships. Applied the reviewed pilot_roles.sql, worker_roles.sql and cleanup_roles.sql
in one transaction on the exact initialised target. New credentials and independent random
session keys are stored only in owner-only Git-ignored per-service files. The owner-provided
Auth0 client secret is included only in the private Vercel settings. The operator URL is
not a runtime credential. No existing role/password was overwritten.

Verified actual Node pg session-role TLS/login, token-table SELECT and membership-read
denial (42501). Independently verified actual TLS logins for API/worker/cleanup, permitted
report reads and denial of token-table SELECT, membership role updates and recovery-state
updates. Recovery remains QUARANTINED; no user/unit bootstrap, paid service or process was
started. A local direct-libpq certificate path initially encoded spaces as plus characters;
passing the trusted CA path as an explicit connection argument resolved it with verify-full
and channel binding retained. Cloud session URL was verified with Node's own trust roots.
Vercel private settings, pilot API binding, recovery bootstrap and local demo processes
remain pending; current BACKEND_API_BASE_URL must be replaced with the selected pilot API
before activating the full preview. No live Auth0 login has been verified.

Subsequent API/activation update: the user created the separate Free web service
https://airshedos-pilot-api.onrender.com on the preview branch. /health returns 200.
Initial readiness showed database=unavailable with sslrootcert=system. An explicit installed
Certifi CA path in the private API DATABASE_URL resolved the hosted connection while
preserving verify-full. The existing API container independently confirmed that CA path.
The owner explicitly approved the separate recovery-state activation after automatic
review rejected an attempt without that explicit permission (the rejected command did not
execute). At 17:15 IST the checked empty bootstrap committed; fresh DB reads confirmed
READY/matching epoch and zero users/reports. Hosted /ready independently confirms
database=ready and recovery=ready, but returns 503 for missing reviewer/worker/cleanup.
No paid services/processes, real reports or reviewer grants were created. See
RECOVERY_ACTIVATION.md. Next user action: set Preview BACKEND_API_BASE_URL to this pilot
API, redeploy the branch preview, and perform the first managed app login. Identity remains
configured_not_live_verified until that signed journey is evidenced.

## Helium inspection checklist

1. Vercel → AirshedOS → Settings → Environments → Production → Branch Tracking shows
   the production branch. Settings → Environment Variables is where APP_MODE is added;
   it is an application setting, not a built-in dashboard control. For design review,
   set APP_MODE=pilot on Preview only, optionally scoped to codex/seva-phase-7, then
   redeploy that preview. Production and the Render branch stay unchanged during setup.
2. Render → airshedos-api → Environment (left pane): inspect current variable names;
   + Add Environment Variable creates a missing key. Inspect deploy/status, health path and existence
   of APP_MODE, DATABASE_URL, AUTH0_* and recovery/storage settings. Record names only.
   Check whether a separate worker and cleanup schedule already exist; do not add a paid
   instance before agreeing on the service/cost.
3. Neon → existing AirshedOS project: confirm project/region/Postgres version, branches,
   database names and whether application tables exist. Historical project ID is
   withered-glade-58447528, but do not assume it is still the selected target. Do not run
   destructive SQL or create production tables from a browser test fixture.
4. Check whether managed Auth0 and private object storage already exist. Configuration
   values stay in their service dashboards; share only names/statuses and blockers.

After these facts are known, prepare exact environment bindings and migration/release order
for the chosen pilot target. Preview APP_MODE=pilot can show the new public website, but
missing identity configuration must continue to show sign-in unavailable. Do not label an
unconfigured preview a functional deployed pilot.
The [Auth0 preview setup](AUTH0_PREVIEW_SETUP.md) records the exact callback origin and
reviewed API profile/scope/application policy, with remaining server configuration gates.

Current official references consulted: [Vercel GitHub deployment](https://vercel.com/docs/git/vercel-for-github),
[Render deploy hooks](https://render.com/docs/deploy-hooks),
[Neon connection guide](https://neon.com/docs/connect/connect-from-any-app),
[Vercel production branch location](https://vercel.com/docs/git),
[Render Environment panel](https://render.com/docs/configure-environment-variables).
