# Phase 6 — evaluation and pilot readiness

11 November 2026 (Asia/Calcutta). Local/private rehearsal; no hosted pilot rollout.
Working checkout: `/Users/aadityajain/Technical Assessments/Onboarding/Google Build Week`.
Actual base/HEAD: `6f071afd10f0ffed024448ac87d3bfae9ec8abc4`.
Branch: `codex/seva-phase-6`. Existing Phase 0–5 source work and unrelated presentation/output
files were preserved. The initial inherited browser run regenerated its Phase 3
screenshot output; Phase 6 now writes dedicated screenshot filenames. Changes remain uncommitted. Nothing was pushed, deployed, sent
to participants, provisioned as a paid service or migrated on a production database.

The supplied Phase 6 prompt broadens the earlier ledger label “release hardening” to
include exploratory evaluation preparation. This report covers actual code and tests,
not a presumed completed deployment. Comprehensive design work stays in Phase 7.

## Readiness and privacy changes

`seva_0006` adds recovery control and a separate worker heartbeat (30 tables total).
Fresh databases begin quarantined. API and worker runtime require an external
SEVA_RECOVERY_EPOCH, with a matching released database control row. This UUID is a
release binding held outside backups, not a login secret or substitute for authentication.
The normal runtime has no dev-principal/bootstrap/release HTTP route. The offline console
requires a separately approved PostgreSQL management session_user and exact target
acknowledgement. Empty bootstrap refuses prior initialisation or existing identities,
reports/media; existing/restored databases require reconciliation instead.

Pilot `/ready` now checks schema/database, configured strict identity verifier,
released matching recovery binding, approved non-prototype triage with a current
approved reviewer, worker heartbeat (45s), cleanup heartbeat (120s) and private storage
configuration by default. An explicitly selected text-only configuration labels images
unavailable. Its cleanup adapter refuses existing objects it cannot purge. Worker pulse
cannot write the retention-health table or approve releases; column grants permit only
inert control-row locking. Required failures return 503, while unconfigured optional
providers are labelled unavailable/degraded without blocking report acceptance. Configured
providers/identity/storage are explicitly **not live verified**. `/health` is liveness only.
Source outages remain visible in normal processing/context responses, never zero readings.

Audit-driven fixes:

- Public prototype mode refuses pilot/private configuration and live provider credentials.
  It stays an isolated synthetic demo, while pilot mode blocks every legacy v1 path.
- Resident detail/list and reviewer queue responses now include content-expiry deadlines;
  open views clear private content and map markers at expiry. Existing detail/evidence/
  image timers remain. This is a privacy correction, not a visual redesign.
- Withdrawal now denies resident/reviewer private-image reads and omits images from
  projections; saved report text remains available within its own policy. Processing
  already rejected withdrawn in-flight results.
- Pilot maps require an explicit build-time purpose/third-party-processing approval flag,
  default off, even when a public Maps key exists. Coordinates can still be entered and
  reviewed in the equivalent permitted list. Browser rehearsal blocks nonlocal requests.
- Optional resident AQ/weather now requires an owned active accepted report in an
  approved case unit; coordinates come from storage, quota precedes provider IO, and
  access is rechecked afterward. The pre-submit form makes no source request; the
  existing context component is available on saved detail. This closes the earlier
  account-only context exception to the paid-case admission boundary.
- The resident form stays disabled until hydration completes, preventing early input
  from being replaced as the interactive form mounts.
- Recovery failures use a specific safe unavailable response rather than incorrectly
  telling the user that text intake is valid during quarantine.

The route audit enumerates the generated API surface and exercises anonymous denial
for all v2 actions/reads and pilot-mode v1 denial. The existing signed resident/unit
matrix remains: ownership and unit filtering before pagination/counts/maps, current
membership on each action, no client-role authority, independent media/evidence/export
checks, separate reporter projections, no shared caching and CSRF-protected mutations.
BFF routes are allowlisted and build server credentials from the managed session.
No cross-user/unit exposure was found in this bounded synthetic matrix; this is not
a claim that no vulnerability can exist. Only explicit reporter updates are public to
the report owner; no public individual-case feed or official agency dispatch exists.

## Isolated restore and restart evidence

The rehearsal uses PostgreSQL 18 `pg_dump -Fc` and `pg_restore` into a **different empty
database**, with a separate copy of private synthetic objects. No live/original database
or object prefix is overwritten. PostgreSQL documents custom archive behavior and warns
that restoring a dump can execute source code; the test uses its own trusted synthetic
archive. [pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html), [pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html).

The archive includes three synthetic reports, two cleaned private objects, retained
synthetic evidence and synthetic session ciphertext. After backup, the source suppresses
one report, deletes another report's media, expires a third report and deactivates a
reviewer. An independently held, current erasure manifest is exported from the source
with a repeatable-read snapshot. It contains only pseudonymous IDs/deadlines and inactive
user IDs, with explicit seven-day coverage, bounded fields and a canonical SHA-256.
Private file modes are enforced. The hash checks integrity, not deletion or provenance.

The restored target's new external UUID blocks valid restored principals even before
quarantine replay. Quarantine invalidates all sessions/token ciphertext, active jobs/
leases/admissions, operator grants and unit memberships. Replay shortens deadlines,
suppresses tombstones and physically removes objects, report/private text, evidence
payloads/hashes and expired metadata before release. Fresh login and offline authority
re-provisioning are required. A surviving resident report remains readable while its
post-backup deleted image is unavailable: the proof does not merely deny all records.

Stale/incomplete/altered manifests, wrong management login, repeat empty bootstrap and
release before cleanup are rejected. Injected object-deletion failure leaves quarantine
in place; retrying cleanup succeeds. Actual PostgreSQL restart preserves the accepted
case/session. Separate worker SIGKILL, expired lease, stale completion, duplicate delivery,
retry exhaustion, source failure, quota-before-invocation and in-flight erasure/revocation
regressions are preserved. Restore cleanup does not convert old evidence into a new
scientific conclusion or resurrect old role/session claims.

**Limits:** this proves logical archive restore plus current authoritative erasure replay
in an isolated local environment. It does not prove a hosted backup's encryption, PITR,
replica scope, seven-day expiry or disaster RPO/RTO. Complete independent erasure-ledger
tail/watermark storage is a live release gate. If the primary is lost and the latest
complete erasure state cannot be established, do not release the restored data. A recent
hash/file alone cannot prove completeness. Source writes must remain frozen through
manifest cutover/replay/release. See [the runbook](PILOT_RUNBOOK.md).

## Software checks and production rehearsal

Final commands/counts are maintained in [PHASE_STATUS.md](PHASE_STATUS.md):
**642 backend tests**, **5 signed identity tests**, **5 resident + 2 reviewer development
journeys**, the same **7 HTTPS production-build journeys**, and **62 legacy Chromium
regressions** pass. Ruff (146 files), lint/typecheck/build, generated contracts, secret
scan, protected hashes and local document links pass. Two existing test dependency
deprecations remain. The full development advisory scan is explicitly not counted as
a zero-findings pass; its remaining moderate issue is described below. The full
backend suite includes actual PostgreSQL rather than SQLite or mocked permissions.
The additional tests cover readiness prerequisites/degradation, all generated routes,
withdrawn media, empty bootstrap, actual database restart/archive restore, cleanup failure,
strict manifest checks and a small measured acceptance sample. Existing substantive
checks are retained, including offline research-unit regressions; no dataset extraction,
training or historical scientific evaluation workflow was run.

`npm run test:pilot` builds Next.js with public Maps disabled, runs its standalone
production server behind local HTTPS, and executes both user journeys through actual
managed-SDK session handling and server-only BFF credentials. The identity provider is
an explicit local signed OIDC fixture. The TLS API and worker are separate processes;
the synthetic worker also runs its cleanup loop. Secure/HttpOnly/host-only cookies are
checked. Test tooling is loopback/database guarded, excluded from the application image
and creates no production login bypass. The initial synthetic queue is held for receipt
assertions and explicitly released; synthetic retry waits are zero, unlike production's
30/120s. Production lease/crash behavior is tested separately against PostgreSQL.

An initial discarded production-browser run exposed a compiled public Maps setting
surviving empty runtime configuration. It is not evidence of provider readiness or
usage/cost. The final rehearsal rebuilds with Maps disabled, gates pilot map activation
and refuses nonlocal browser traffic. Existing development journeys and the legacy
browser suite are separately retained. No real Auth0 tenant, R2 host, hosted worker,
production migration, recruited reviewer or cloud-provider availability is claimed.

## Dependency hardening

Installed stack was inspected: FastAPI 0.141.1, Pydantic 2.13.5, SQLAlchemy 2.1.8,
Alembic 1.20.1, psycopg 3.3.8, Python 3.13.5, Next.js 16.4.6 and Auth0 SDK 4.33.0.
Web commands use the installed Node runtime (25.9.0 in the web checkout); the root shell
also exposed 24.14.1. No framework/cloud migration or model dependency change was made.

Advisory-driven runtime changes only: certifi 2026.7.22 → 2026.10.18,
opentelemetry-api 1.44.0 → 1.45.1, Pillow 12.3.0 → 13.0.0,
pyasn1 0.6.4 → 0.6.5, urllib3 2.7.0 → 2.8.0 and frontend transitive source-map-js
1.2.1 → 1.2.2. Pillow's existing `<14` range permitted the security release; its minimum
is now 13. Other Python pins were constrained unchanged. Runtime and dev locks were
regenerated. Compatible brace-expansion/Zod/TypeScript ESLint development dependency
updates removed high-severity development findings; no unsupported major override.

References: [Pillow 13 security/release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html),
[certifi advisory](https://github.com/advisories/GHSA-6q48-6c7w-9gw2),
[OpenTelemetry advisory](https://github.com/advisories/GHSA-xcq7-p3pf-p88h),
[pyasn1 advisory](https://github.com/advisories/GHSA-2qm8-x737-gmw5),
[urllib3 advisory](https://github.com/advisories/GHSA-vxq7-64xx-v4gw),
[source-map-js advisory](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).

The runtime Python advisory scan covers 61 locked packages with zero reported advisories;
`npm audit --omit=dev` also reports zero. These are dated advisory checks, not proof of
zero vulnerabilities. The full frontend development scan still reports **seven moderate
nodes from one minimatch advisory** through TypeScript ESLint. The maintained parser's
current compatible range remains 10.x; the published fix is 11.0.1. This is tracked
build-tooling exposure, not a production runtime dependency, and must be reviewed before
processing untrusted build inputs. No forced incompatible override or full-audit “pass” is
claimed. [Remaining minimatch advisory](https://github.com/advisories/GHSA-g3hv-75wg-m249).
Machine-readable audit records are in [evidence/phase6](evidence/phase6).

## Actual measurements and evaluation status

[evidence/phase6/acceptance.json](evidence/phase6/acceptance.json) records **six sequential
synthetic text-only HTTP submissions**, two residents, concurrency one, FastAPI TestClient
plus local Docker PostgreSQL 18, no network/AI work in acceptance. The recorded median
is 13.118 ms (range 11.307–40.669 ms). These samples, rather than a capacity promise,
are the actual software observations. The recorded median,
range and individual samples describe only that test condition. They establish neither
production capacity nor human preparation/review savings. Usage counters are admission
units, not exact paid billing. No hosted cost or human task time was measured.
[evidence/phase6/restore.json](evidence/phase6/restore.json) records one small synthetic
archive/replay timing sample and its archive size. It is not a recovery-time objective.

[Exploratory set v1](evaluation/v1/cases.json): **12 project-authored synthetic stress
scenarios**, 8 development and 4 reserved, split/checksum in [manifest](evaluation/v1/manifest.json).
**Zero field cases, zero real reviewers, zero faculty/student proxies and zero walkthroughs.**
The reserved scenarios are unused for participant evaluation; no blinded/labelled accuracy
benchmark is claimed. A 30–50 credible-case target is conditional on permissions, source
quality and domain review. The lack of appropriate field evidence/recruitment is an
explicit external limitation, not an excuse to fabricate a count.

[Protocol v1](evaluation/v1/PROTOCOL.md) specifies matched baseline/product tasks,
preparation/review timing, equivalent evidence, AB/BA order and matched-case rotation,
completeness and uncertainty-comprehension rubrics, rater disagreements, missing/unfinished
pairs and separate real/proxy/synthetic reporting. The CSV template contains no participant
rows. A 3–5-person walkthrough and a later 5–10-reviewer pilot are recruitment targets
only. No invitation, interview, adoption, benefit percentage or scientific accuracy was
invented. MODEL_NOT_ACCEPTED and protected historical records remain unchanged.

## Handoff and outstanding release gates

Use [PILOT_RUNBOOK.md](PILOT_RUNBOOK.md), [pilot.env.example](pilot.env.example) and
[PILOT_RELEASE_CHECKLIST.json](PILOT_RELEASE_CHECKLIST.json).
Default next step is owner-approved private/staging preparation, with live identity,
private storage/regions/deletion, independent erasure journal/backup policy, actual host
worker/cleanup lifetime, unit roster, provider terms/budgets, notices and security review.
Real-data collection/public deployment/spending/outreach remain unauthorised here.
The software implementation can be locally verified while those external checks and
human evaluation remain pending. Phase 7 may refine the completed flows visually; this
phase adds no rebrand, speculative dashboard or custom forecasting model.
