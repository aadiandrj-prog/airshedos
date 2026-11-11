# Render pilot service plan — not applied

11 November 2026. Existing web API remains on main. No billable service has been created.
This is a reviewable deployment plan; provider usage, taxes and hosted-region/backup terms
are separate. Source code and the PostgreSQL queue remain shared; no new broker.

**Owner decision: keep preview only for now.** Do not create these paid services. The
following plan is retained for a later explicit budget decision. The current preview
is a design/configuration preview, not a ready hosted report-processing pilot.

| Service | Source / command | Proposed compute | Purpose |
|---|---|---|---|
| Existing airshedos-api | apps/api Docker image; normal uvicorn CMD | Keep current Free initially, or paid smallest web compute | API; free hosting can cold-start |
| airshedos-pilot-processing | same repo, codex/seva-phase-7, apps/api; `python -m app.processing` | Smallest paid worker (Starter / 0.5c-512mb) | Continuous durable PostgreSQL worker |
| airshedos-pilot-cleanup | same repo/branch/image; `python -m app.resident.maintenance` | Smallest cron compute; `* * * * *` | Separate restricted-role expiry/deletion pass each minute |

Render's published small compute example is $7/month. Cron is billed for active runtime
with a minimum $1/month per cron service. Thus a worker plus cron starts around $8/month;
adding the paid web API makes the base around $15/month. These are planning figures, not
an all-in quote or measured cost. Confirm the displayed plan and charges in the dashboard
before creating anything. No Pro workspace upgrade is needed for this plan. No paid
Google/provider request is authorised or needed for setup/recovery checks.

References: [Render compute example/prices](https://render.com/articles/set-up-self-hosted-github-actions-runners-on-render),
[cron billing](https://render.com/docs/cronjobs), [pricing](https://render.com/pricing).

## Required configuration before activation

Worker: `APP_MODE=pilot` (lowercase), its own `SEVA_WORKER_DATABASE_URL`, shared released
`SEVA_RECOVERY_EPOCH`, bounded attempts/quotas and reviewed source/storage settings.
Cleanup: its own `SEVA_CLEANUP_DATABASE_URL` and private-media deletion credentials, or an
explicitly selected text-only profile (`PILOT_MEDIA_REQUIRED=0`). It must not use API/BFF
credentials or the Neon owner login. The reviewed `scripts/cleanup_roles.sql` supplies
retention permissions without token ciphertext reads, membership grants or release writes.
All runtime roles must be non-owner logins without extra role memberships/elevated flags;
Neon's owner/default elevated role is reserved for offline administration.

Keep automatic deploy off for new worker/cron until schema, roles and the recovery binding
are ready. The standalone worker's start command overrides uvicorn; the cron Docker command
must also override uvicorn and exit after cleanup. Keep worker and cleanup credentials
separate rather than sharing the whole environment group with every service.

Before switching the API: migrate the selected empty target; initialise its empty recovery
binding; configure managed identity and complete an actual signed login to establish the
owner's verified identity; bootstrap the approved operator/unit; configure the triage UUID;
start worker and cleanup; verify current heartbeats and /ready. The SDK can save its verified
session before the API is fully ready; the workspace may honestly remain unavailable during
that bootstrap. No fake principal, unverified email linking or HTTP bootstrap route.

Creating a new continuous worker can keep Neon compute active. Check the actual Neon plan
and usage allowance; no free-tier capacity or zero-cost promise is made. Optional provider
retention stays off until its storage/backup terms are approved. The final private pilot
still needs hosted identity, deletion, worker restart and recovery rehearsals.
