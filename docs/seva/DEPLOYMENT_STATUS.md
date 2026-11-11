# Deployment and GitHub publication

11 November 2026. User authorised GitHub publication and checking Render, Vercel and Neon.
The user is operating the hosting dashboards in Helium; automated Helium access was not
approved. No credential value is requested in chat or stored in this record.

## Source and current public services

Implementation commit: `2121566` on `codex/seva-phase-7`, preserving base `6f071af`.
The deployment branch is prepared for publication; production main remains `142dfc1`.
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
No hosted migration, billable worker or new paid service has been authorised/provisioned here.

## Helium inspection checklist

1. Vercel → AirshedOS → Settings: confirm apps/web root, production branch and APP_MODE
   existence/target (Preview vs Production). Inspect current deployment commit/status.
2. Render → airshedos-api: inspect branch, current deploy/status, health path and existence
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
[Neon connection guide](https://neon.com/docs/connect/connect-from-any-app).
