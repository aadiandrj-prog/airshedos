# Private pilot release and recovery runbook

Phase 6, 11 November 2026. Prepared for an owner-approved private/staging pilot.
This document does not authorise spending, public deployment, live collection, messages
or a production migration. Code is published on the phase-7 branch; the new hosted pilot is
not yet configured. See [deployment status](DEPLOYMENT_STATUS.md), [the environment template](pilot.env.example),
[phase validation](PHASE_6_VALIDATION.md) and the actual [status ledger](PHASE_STATUS.md).

## Release order and operational meaning

1. Freeze/review the exact revision and permissions. Preserve unrelated working files.
   Review dependency advisories and generated contracts. Separate management/migration,
   API, BFF session, worker and cleanup logins. API and worker must not read token ciphertext;
   worker must not alter membership grants, erasure state, release approval or cleanup health.
2. Establish an explicitly selected isolated PostgreSQL target and private object store.
   Confirm TLS, regions, private bucket/public-domain settings, lifecycle, backup scope and
   at-most-seven-day encrypted backup retention with the owner. These settings are external
   capabilities to verify; putting BACKUP_RETENTION_DAYS in an env file configures no host.
   Originals, raw provider payloads and Google-derived saved values are excluded.
3. Quiesce traffic/workers before migrations. Rehearse `alembic upgrade head` through
   `seva_0006` with separate management credentials on a disposable loopback database.
   Ordinary Alembic intentionally refuses hosted targets. After owner approval of the exact
   hosted target, use the checked offline command described below; never point a test fixture
   at Neon. Runtime never runs create_all/migrations. Apply reviewed API/session, worker and
   cleanup grant scripts after migration. Runtime roles must be non-owner logins without
   elevated flags or extra memberships; Neon owner/default elevated credentials are offline only.
4. For a genuinely empty install only, generate a fresh recovery UUID outside the database,
   store it as SEVA_RECOVERY_EPOCH in API/worker configuration, and use the offline
   `python -m app.operations initialise-empty --target-database NAME --epoch UUID` command.
   It requires the approved management session_user and refuses existing reports/media
   or a previously initialised/restored database. There is no web bootstrap/dev login.
   For an existing database, follow quarantine/manifest reconciliation below instead.
5. Configure official managed identity, exact callbacks/logout origins and ten-minute
   API access-token profile. Configure strong independent cookie/session-encryption secrets,
   server-only session storage and exact HTTPS origins. Keep AUTH_ALLOW_LOCAL_HTTP absent
   in production. Verify actual tenant token/refresh/logout/back-channel behavior separately.
   Operator provisioning binds exact verified issuer/subject; never infer role from email.
6. On an empty installation, complete a real Auth0 sign-in after configuring the session
   database to create the exact verified issuer/subject identity. The SDK saves this session
   independently of API workspace readiness; a temporarily unavailable workspace is expected.
   Use offline operator provisioning to bootstrap that existing identity and approve the unit,
   initial administrator/reviewer and PILOT_TRIAGE_UNIT_ID. Never bootstrap by email or add
   an HTTP dev-login route. Then start independent API, continuous worker and scheduled cleanup processes. Worker command:
   `python -m app.processing`. Cleanup: `python -m app.resident.maintenance`, at least each
   minute, with separate deletion credentials. Worker reads use a separately scoped object
   credential where the host supports it. Test the host's worker lifetime/restart and cleanup
   scheduling; a web-request task is not a worker. Reviewed worker/Docker examples exist,
   but root render.yaml still provisions no pilot worker and has not been activated.
7. Start the Next.js production build behind HTTPS. Only public allowlisted build settings
   may enter the bundle. Pilot maps default off even if an old public Maps key exists.
   Enable NEXT_PUBLIC_PILOT_MAPS_APPROVED only after purpose/third-party location processing,
   permitted use and region review; rebuild and verify the bundle. Manual coordinates and
   equivalent scoped list remain available. Backend context/provider permission is separate.
8. `/health` proves process liveness only. `/ready` requires schema, configured strict
   identity verifier, matching released recovery UUID, worker heartbeat within 45 seconds,
   cleanup within 120 seconds and private-media configuration by default. Explicit
   PILOT_MEDIA_REQUIRED=0 allows text-only readiness, labelled images unavailable. Text-only
   cleanup refuses existing private objects without a storage adapter. Optional provider
   configuration is labelled unverified/unavailable and does not make a required check pass.
   Do not interpret configured_not_live_verified or HTTP 200 as provider/scientific readiness.
9. Before owner-approved real collection, rehearse real Auth0, R2 privacy/deletion, backup
   expiry, independently durable erasure-ledger export, roles, worker kill/recovery and
   the actual host's upload/response limits. Confirm triage/unit roster, budgets, notices,
   consent and purpose. Keep retained provider approval off until source/backup review.
   Any public rollout or outreach requires separate authorisation.

Resident source context is requested from saved report detail, using an owned accepted
report and approved routing. Pre-submit context makes no source call. Do not restore
the former arbitrary-coordinate account-only context path or bypass quotas during a demo.

## Checked hosted schema upgrade

The exact initial Neon production/neondb upgrade was separately approved and completed on
11 November 2026. See [execution/verification record](NEON_SCHEMA_CHANGE.md). Do not rerun
the empty-install command on that now-initialised database. Instructions below describe
the controlled workflow for a separately approved target, not an automatic next action.

First verify the exact direct endpoint, database name and offline operator login in the
selected Neon branch. Keep its connection string out of chat, command arguments and logs.
Supply SEVA_MIGRATION_DATABASE_URL privately through the process environment, using
`postgresql+psycopg`, `sslmode=verify-full` and `sslrootcert=system` (or an approved absolute
CA file). The installed psycopg/libpq must support that CA option. A pooled endpoint,
connection query overrides, missing CA/password or a mismatched target is refused.

After reviewing and authorising the concrete target, from apps/api run:

```sh
python -m app.persistence.migrate \
  --host EXACT_DIRECT_HOST --database EXACT_DATABASE --operator-role EXACT_LOGIN \
  --expected-revision empty --acknowledge-target
```

`empty` refuses any existing user relation, including another schema. For an existing
installation, inspect its exact revision and substitute that `seva_####` value; never
substitute `head` for the expected starting state. The command acquires an operator lock,
checks the connected database/session identity, applies only forward migrations through
the checked-in head and verifies it before one transaction commits. Failed DDL rolls back;
safe reason codes omit database exception details and credentials. It does not provision
roles, release quarantine, create identities or activate services. Initial schema is
seva_0006 with 30 application tables plus alembic_version; recovery remains QUARANTINED.

Review and apply `scripts/pilot_roles.sql`, `scripts/worker_roles.sql` and
`scripts/cleanup_roles.sql` through the offline operator connection, binding only the
dedicated role names. These scripts do not create roles/passwords. The cleanup role can
purge protected content but cannot read token ciphertext or change access/recovery grants.
Review backup/retention and external erasure-ledger arrangements before real collection.

## Bounded failure response

- Readiness 503: inspect safe check codes; never log tokens, bodies, coordinates, images,
  full URLs/query strings or provider exceptions. Production reverse-proxy access logging
  must omit protected URI/query/body/header data. Request metrics contain method/status/time.
- Worker stops: accepted reports remain saved and human review remains usable. Readiness
  turns unavailable after the bounded heartbeat interval. Restart the separate process;
  leases recover after timeout. At most three deliveries; exhausted jobs are visible and
  need an authorised, reasoned refresh after fixing the cause. A usable partial version
  stays frozen. External calls can be billed more than once after a crash.
- Cleanup fails: stop retained collection, preserve deletion keys for retry, keep suppressed
  records inaccessible. Fix storage/permissions and retry until physical purge and backlog
  checks pass. Read-time denial is not a physical deletion receipt.
- Source/identity failure: configuration/permission errors need operator correction; transient
  analysis failures use bounded retry. Never fabricate a reading or clear a report. Auth
  failures deny access. No emergency production fake principal or role header is permitted.
- Suspected exposure: stop private traffic/workers, quarantine with a new external UUID,
  revoke affected sessions/credentials through approved procedures, preserve minimised
  security evidence and investigate scope. Do not publish private evidence in an incident log.

## Isolated restore and erasure replay

PostgreSQL [pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html) / [pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html)
custom archives were rehearsed locally. Restore can execute source database code: use a
trusted reviewed archive, an isolated empty destination, and restricted operator control.
Never use `--clean`/`--create` against a live database. The local test used a distinct database
and a distinct copy of synthetic private objects; the original database was not overwritten.
Do not mount the original/live object prefix into the restored environment.

Before taking a cutover manifest, freeze source writes, including new deletion/expiry
policy changes, and finish exporting the authoritative deletion ledger to independent
private storage. `export-manifest` uses a repeatable-read source snapshot. The manifest
contains pseudonymous IDs/deadlines and inactive-user IDs, no text/coordinates/images.
Keep its directory private (0700), file 0600, encrypted in real backup operations, with
restricted access and approved expiry. Record its SHA-256 via a trusted operator channel.
The hash is integrity metadata, not provenance, completeness, encryption or deletion.

Set a NEW SEVA_RECOVERY_EPOCH outside the archive before starting any restored API/worker.
Old READY rows do not match it, so valid old sessions cannot read the restored records.
Keep ingress disconnected as an additional control. Execute with the offline recovery
management URL/approved session_user and exact target-database acknowledgement:

```sh
python -m app.operations quarantine --target-database TARGET --epoch NEW_UUID
python -m app.operations apply --target-database TARGET --epoch NEW_UUID \
  --manifest /private/operator-ledger/manifest.json --manifest-sha256 REVIEWED_SHA256 \
  --backup-at BACKUP_START_ISO_TIME --ack-source-writes-frozen
python -m app.operations release --target-database TARGET --epoch NEW_UUID \
  --manifest-sha256 REVIEWED_SHA256 --ack-source-writes-frozen
```

Replay requires a canonical, unmodified, fresh manifest (five-minute admission window),
backup within its seven-day coverage and no omitted restored report/media IDs. It shortens
restored TTLs; suppresses deleted reports; removes deleted/expired private objects,
snapshots, payloads/hashes and private text; and purges elapsed audit records. A failed
object deletion, stale/incomplete manifest or missing cleanup receipt leaves quarantine
in place. Retry after correction. Quarantine clears all restored token ciphertext/sessions,
active leases/admissions, processing/cleanup heartbeats and operator grants, and suspends
all unit memberships. Fresh login and offline re-provisioning are required. Historical
review/evidence meaning is retained except explicit erasure/expiry tombstones.

After replay, independently inspect own/other unit access, media/object inventory,
expired/erased payloads, clean heartbeat and operator approvals. Start/restart the continuous
worker, verify `/ready`, then authorise private ingress. Never reuse a backup's old UUID
or claim that an arbitrary recent manifest proves the lost primary had no newer deletions.
An unplanned disaster requires independently durable, complete erasure-ledger coverage;
if its last tail/watermark cannot be established, **do not release restored data**. That
live journal/backup/PITR arrangement is not configured by this local implementation.
The local test proves replay given a current authoritative manifest, not disaster RPO/RTO
or actual host encryption/replica/backup expiry. Downloaded/browser copies cannot be recalled.

## Repeatable local demonstration and fallback

Use only the explicitly named disposable loopback database/user described in DEVELOPMENT.
Run backend checks with TEST_DATABASE_URL and SEVA_TEST_PG_CONTAINER; never reset that database
while a browser/identity harness is running. Run `npm run test:identity`, `test:resident`
and `test:authority`. Then `npm run test:pilot` builds with public Maps disabled and runs
both journeys on the standalone production build, HTTPS secure host-only cookies,
local synthetic signed OIDC, separate TLS API and separate worker/cleanup process.
The harness blocks nonlocal browser requests and cleans temporary certificates/private files.
It is test-only tooling excluded from the application image, not a production auth bypass.

Demonstrate: resident sign-in → text/photo receipt → own list/reload → reviewer unit queue
→ internal note → queued analysis → controlled provider timeout → continued human review
→ explicit question/reply → recorded pilot follow-up → separate public update → metadata
export. Show second-resident/other-unit denial and admin proposal/revocation. Explain
unknown capture time, advisory support, forecast window peaks and no official dispatch.
The initial synthetic queue is deliberately held until explicit release, and synthetic retry
waits are zero for determinism; production waits remain 30/120s. A separate subprocess
SIGKILL test proves actual lease recovery. No real provider call is needed for this demo.

When cloud identity/storage/reviewers are unavailable, use this guarded local synthetic
workflow or the versioned synthetic task packet. Label it synthetic; do not show a fake
production login, official receipt, recruited user or measured benefit. The exploratory
[protocol](evaluation/v1/PROTOCOL.md) governs later matched tasks. No invitation was sent.
