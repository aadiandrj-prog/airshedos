# Deployment and GitHub publication

11 November 2026. User authorised GitHub publication and checking Render, Vercel and Neon.
The user is operating the hosting dashboards in Helium; automated Helium access was not
approved. No credential value is requested in chat or stored in this record.

## Source and current public services

Implementation commit: `2121566` on `codex/seva-phase-7`, preserving base `6f071af`.
Published branch head: `5198f0f185b4d67baf19295a83b126939f52d466` (publication handoff).
The GitHub push succeeded; production main remains `142dfc1`.
Vercel reported a successful Preview deployment for this head.
Remote [GitHub checks](https://github.com/aadiandrj-prog/airshedos/actions/runs/42985112535) completed successfully:
backend (including actual PostgreSQL and signed resident/reviewer journeys), legacy browser,
frontend and secret jobs all passed for `5198f0f`. Subsequent documentation-only publication
does not change the validated application source; its checks are tracked separately.
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
| Neon | Historical docs record an empty reserved project; current dashboard/schema not yet independently verified |

No paid provider, real report, authentication or private-media call was made by these probes.
A green old-prototype /ready does not verify the new pilot or its database connection.

The preview deployment URL is [airshedos-agrlq8s4u-grease-liquor.vercel.app](https://airshedos-agrlq8s4u-grease-liquor.vercel.app).
Anonymous HTTP requests redirect to Vercel sign-in; the resulting HTTP 200 is the login page,
not an independently verified app render. The attempted anonymous asset probe therefore
does not establish that deployed app bundles were inspected. No remote asset-scan pass
is claimed; the local final build/secret gates and remote secret job passed.

The user confirmed Vercel root `apps/web`, Render branch `main` and root `apps/api`.
They could not locate APP_MODE/identity/database settings, which does not independently
prove the values are absent. They report an archived Neon branch named `primary` whose
compute was suspended two months ago; project identity and actual schema remain pending.

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

Current official references consulted: [Vercel GitHub deployment](https://vercel.com/docs/git/vercel-for-github),
[Render deploy hooks](https://render.com/docs/deploy-hooks),
[Neon connection guide](https://neon.com/docs/connect/connect-from-any-app),
[Vercel production branch location](https://vercel.com/docs/git),
[Render Environment panel](https://render.com/docs/configure-environment-variables).
