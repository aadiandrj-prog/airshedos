# Deployment and GitHub publication

11 November 2026. User authorised GitHub publication and checking Render, Vercel and Neon.
The user is operating the hosting dashboards in Helium; automated Helium access was not
approved. No credential value is requested in chat or stored in this record.

## Source and current public services

Implementation commit: `2121566` on `codex/seva-phase-7`, preserving base `6f071af`.
Published branch head before the deployment-prerequisite follow-up: `e86abac66ac2efee269e8d45ee0c94942f65db4a`.
The GitHub push succeeded; production main remains `142dfc1`.
Vercel reported a successful Preview deployment for this head.
Remote [GitHub checks](https://github.com/aadiandrj-prog/airshedos/actions/runs/42987003154) completed successfully:
backend (including actual PostgreSQL and signed resident/reviewer journeys), legacy browser,
frontend and secret jobs all passed for `e86abac`. The earlier `5198f0f` run also passed.
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
| Neon | User inspected project airshedos, branch production: no tables; no independent database connection made |

No paid provider, real report, authentication or private-media call was made by these probes.
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
No unarchive/restore operation is indicated. The production branch has no tables according
to the user's Tables inspection. Host, database name, role and backup policy remain to verify.

The user created the Auth0 regular web application and supplied its public domain/client
identifier. Callback/API/refresh configuration and live sign-in are still pending. The
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
No hosted migration, billable worker or new paid service has been provisioned here.
The [reviewable Render service plan](RENDER_PILOT_PLAN.md) describes roles, commands and
estimated base charges. The user selected **keep preview only for now**; do not create paid
services. This leaves continuous hosted worker/cleanup readiness pending, with no bypass.

## Deployment-prerequisite follow-up

Added `python -m app.persistence.migrate`, an offline operator command with explicit exact
host/database/login and expected revision acknowledgement. Hosted targets require a direct
connection and verified TLS/CA. The command rejects connection overrides, nonempty initial
targets, revision mismatch and concurrent migrations; all DDL/checks share a transaction.
Ordinary Alembic retains its loopback guard. This prepares a reviewable hosted workflow;
it has not been run on Neon. See the [release runbook](PILOT_RUNBOOK.md).

Added a separate restricted cleanup-role grant script. Actual PostgreSQL coverage verifies
content/media and eventual tombstone purge without token ciphertext reads, membership grants,
recovery release writes or worker-heartbeat writes. No runtime uses owner credentials.

Local follow-up checks: `TEST_DATABASE_URL=<guarded loopback synthetic target>
SEVA_TEST_PG_CONTAINER=airshedos-deploy-pg .venv/bin/pytest -q`: **657 passed**, 51.91s,
two existing FastAPI/Starlette deprecation warnings. Includes 14 checked-migration tests
(actual PostgreSQL atomic rollback, operator concurrency, exact revision and empty-target
guards) and restricted cleanup-role purge/denial coverage. Ruff lint/format: PASS, 148 files.
Signed SDK/session/BFF/Python identity: **5 passed**, zero skips, 2.99s; the deliberately
injected identity-provider outage failed closed. Generated OpenAPI/receiver contracts are
unchanged. Secret scan: PASS, zero findings; git diff --check: PASS. No remote DB query or
paid call was part of these checks. Hosted migration TLS/credentials remain unrehearsed.

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
