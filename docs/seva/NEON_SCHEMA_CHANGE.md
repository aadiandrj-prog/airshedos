# Neon initial schema change — completed and verified

11 November 2026. The owner explicitly approved database initialisation in the setup
conversation. The checked migration committed and its result was independently read back
from the target on 11 November 2026 at 15:34 IST (10:04 UTC).
The owner selected preview only and no paid worker/cleanup provisioning.

## Exact target and evidence

- Project: airshedos; branch: production.
- Direct host: ep-calm-resonance-b30pga6o.c-4.ap-southeast-1.aws.neon.tech.
- Database: neondb; offline migration login: neondb_owner.
- Owner ran the read-only catalog query: PostgreSQL 18.6 (ac70818), zero user relations.
  This is owner-provided evidence, not an independent authenticated probe by the agent.
- Application migration source: published commit 6d95f5db0336c614a9cae4e8d014138472e734cb.
  All four GitHub jobs passed for that commit:
  https://github.com/aadiandrj-prog/airshedos/actions/runs/42993136042.

## Executed change

Ran only the checked forward migration through seva_0006. It created 30 application
tables plus the Alembic revision table and inserts the initial QUARANTINED recovery-control
record. It does not seed synthetic reports, users, reviewer memberships or real cases.
It does not initialise/release the recovery epoch, apply runtime-role grants, change
Vercel/Render branches, start workers, invoke providers or create paid services.

The command independently checks the exact connected database/login, verified TLS/CA,
an empty starting catalog and an operator migration lock. All DDL and final revision
validation share one transaction. A mismatch or error refuses/rolls back the command.
After success, rollback would be a separate explicitly approved database change; no
automatic downgrade or deletion is proposed. Runtime services must later use separate
restricted roles rather than this owner login.

From apps/api, with the secret supplied privately through SEVA_MIGRATION_DATABASE_URL:

```sh
python -m app.persistence.migrate \
  --host ep-calm-resonance-b30pga6o.c-4.ap-southeast-1.aws.neon.tech \
  --database neondb --operator-role neondb_owner \
  --expected-revision empty --acknowledge-target
```

The private URL must use postgresql+psycopg, sslmode=verify-full, sslrootcert=system
(or an approved absolute CA file) and the direct endpoint. The password must not be
pasted into chat, command arguments, tracked files or logs. The redacted URL shared
in chat was insufficient to connect. The owner separately supplied the full URL in the
owner-only Git-ignored local file. No connection string or password was printed or committed.

## Actual hosted verification

The first connection using sslrootcert=system failed certificate-chain verification before
authentication/DDL. The installed libpq 18.0.6 client did not locate a usable system trust
chain. The installed Certifi bundle was then supplied by absolute path, preserving
sslmode=verify-full and channel_binding=require; no TLS verification was disabled.
A read-only connection confirmed the exact database/session login and zero existing user
relations before retrying the already approved operation. No new dependency was installed.

The checked migration then committed. A fresh connection confirmed:

- PostgreSQL 18.6 (ac70818), Alembic revision seva_0006.
- Exactly 30 application tables plus alembic_version; inventory matches ORM metadata.
- All domain tables empty, including users, reports, cases, sessions and memberships.
- Only alembic_version and recovery_control contain a row (one each).
- Recovery state QUARANTINED and epoch NULL: no access release was performed.

No runtime role, grant, recovery initialisation, unit bootstrap, deployment-branch switch,
provider request, worker or paid service was created by this operation. Hosted login,
resident/reviewer journeys and runtime-role isolation still require their separate checks.
The schema command's deterministic transaction/permission checks previously passed locally
and on GitHub for source 6d95f5d. The local trust-bundle correction affects this operator
connection; actual Render/Vercel TLS configuration still needs verification on those hosts.

References: [PostgreSQL TLS verification](https://www.postgresql.org/docs/18/libpq-ssl.html),
[Certifi trust bundle](https://certifiio.readthedocs.io/en/latest/).

## Approval boundary

The phase instructions explicitly require separate authorisation for a production database
migration. The target branch is named production, so approval of this exact initialisation
was obtained before credential setup/execution. A read-only empty-catalog result alone is
not that approval. No hosted reporting or login readiness is claimed by this schema change alone.
