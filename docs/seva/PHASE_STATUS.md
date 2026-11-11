# AirshedOS implementation phase status

Updated: 11 November 2026 (Asia/Calcutta).
Contract: [IMPLEMENTATION_BLUEPRINT.md](IMPLEMENTATION_BLUEPRINT.md).
Decisions: [DECISIONS.md](DECISIONS.md).

## Source and scope

- Selected checkout: `/Users/aadityajain/Technical Assessments/Onboarding/Google Build Week`.
- Audited base: `6f071afd10f0ffed024448ac87d3bfae9ec8abc4`.
- Published deployment branch before the prerequisite follow-up: `e86abac66ac2efee269e8d45ee0c94942f65db4a`.
- Local branch: `codex/seva-phase-7`, preserving the prior Phase 0–6 worktree.
- Phase 0–7 implementation committed for GitHub publication; unrelated presentations/output are preserved.
- The phase reports describe their historical local handoffs. Current publication and
  hosting checks are tracked in [DEPLOYMENT_STATUS.md](DEPLOYMENT_STATUS.md).
  No hosted migration, paid provisioning or external message has occurred.

## Phase ledger

| Phase | Status | Actual output / next dependency |
|---|---|---|
| 0 — Baseline and blueprint | COMPLETE_LOCALLY_VERIFIED | [Baseline](PHASE_0_BASELINE.md), contract and decisions |
| 1 — Persistence foundation | COMPLETE_LOCALLY_VERIFIED | [Phase 1 report](PHASE_1_PERSISTENCE.md), durable repositories/private media/retention |
| 2 — Identity and access | COMPLETE_LOCALLY_VERIFIED | [Phase 2 report](PHASE_2_ACCESS.md), SDK/session verification, scoped APIs, provisioning and shared limits |
| 3 — Resident interface | COMPLETE_LOCALLY_VERIFIED | [Phase 3 report](PHASE_3_RESIDENT.md), authenticated intake/receipt/list/detail/replies and private adapter |
| 4 — Authority dashboard | COMPLETE_LOCALLY_VERIFIED | [Phase 4 report](PHASE_4_AUTHORITY.md), scoped human review, follow-up, explicit publication, bounded enrichment, admin and metadata export |
| 5 — Durable automatic processing | COMPLETE_LOCALLY_VERIFIED | [Phase 5 report](PHASE_5_PROCESSING.md), separate PostgreSQL worker, fenced leases, bounded retries, partial snapshots, quotas and metrics |
| 6 — Evaluation and pilot readiness | COMPLETE_LOCALLY_VERIFIED | [Phase 6 validation](PHASE_6_VALIDATION.md), executable readiness/quarantined restore, local HTTPS rehearsal, privacy fixes and evaluation protocol; live checks/recruitment pending |
| 7 — Comprehensive UI polish | COMPLETE_LOCALLY_VERIFIED | [Phase 7 report](PHASE_7_POLISH.md), light pilot home/resident/reviewer UI, rendered evidence and strengthened keyboard/revocation checks |

The supplied phase prompts govern scope and supersede the original inferred worker/
reviewer numbering. The user-requested pause was honored; work resumed only on request.

## Current behavior

Managed Auth0 SDK sessions are sealed in PostgreSQL. FastAPI independently verifies
access-token type/signature/issuer/audience/client/expiry, bound active app session
and current account/unit membership. Ownership/unit predicates apply before list/
count/search/map pagination and independently to detail, actions, export and media.
The BFF allowlists paths, checks CSRF and forwards server credentials only. Private
projections and no-store responses exclude internal notes and other identities.

Residents can submit text/optional consented cleaned images, recover a lost receipt
without duplication, list/view their own reports and reply to deliberate information
requests. Acceptance commits report/case/pending work before returning a receipt and
has no AI dependency. Unknown incident time remains unknown. Visual processing is
not applicable without an image; known analysis failures now display honestly.

Approved-unit reviewers have a filtered/paginated queue with an equivalent optional
map, case detail, declared facts, private images, source/time/evidence versions,
assignment, private notes, review reasons, pilot follow-up and audit history. Closure
and explicit reopening require reasons; closure waits for open follow-ups to end.
Expected revisions prevent silent competing writes. Analysis never acknowledges,
verifies, closes or publishes automatically.

Public messages/questions have separate fields, previews and explicit publication.
The resident reply returns to the reviewer without overwriting the original report
or frozen evidence. Follow-up findings and closure record human statements, not
proof that pollution was eliminated or that an agency dispatched staff. Manual
external references send nothing. Unit admins propose/suspend only within scope;
operator approval remains separate and proposals grant no access or notifications.

Report acceptance and durable scheduling share one transaction. A separate worker now
claims PostgreSQL leases, heartbeats and retries at most three deliveries; stale or
revoked work cannot publish. Reviewer refreshes return 202 and repeated clicks join
the active run. A new request freezes a new evidence version without changing previous
history, human review or reporter publication. Partial source success is preserved;
wholly failed transient attempts use bounded 30/120-second retry waits. Historical
MANUAL_ENRICHMENT is excluded from polling and abandoned manual jobs are terminalised.

Text-only support is insufficient with no visual hypothesis. Saved assessment excludes
Google Maps values/derived hashes; optional live AQ/weather/forecast is separate and
expires within 15 minutes. Paid context remains CSRF-protected POST, with no coordinate
query URLs. Source retention defaults off; approved source work additionally requires
fresh cleanup health and a shared PostgreSQL quota debit before each configured source
operation. Metrics record source/outcome/latency/admission units without private payloads.
Retention invalidates leases, purges protected data and expires metrics/jobs/audit rows.

Phase 6 readiness also requires a released external recovery UUID binding and current
triage/reviewer/worker/cleanup prerequisites. Restore uses a separate target, canonical
current erasure manifests and physical cleanup before release; all restored sessions,
grants and leases are invalidated. Source contexts require an owned accepted/routed report.
Open private views clear on expiry, withdrawal denies media, and pilot maps default off.
A prepared synthetic evaluation split/protocol is separate from any field/user validation.

The new pilot_case_packet_v2 export preserves recent review/evidence provenance and
canonical SHA-256 with explicit totals/truncation. It omits identity, exact location,
private text, media and provider payloads. Existing pilot metadata v1 and legacy
pollution_event_v1 remain unchanged. No government delivery or receipt is claimed.
Pilot mode blocks v1; the default prototype remains separate and process-local.

## Phase 6 local verification (historical)

Phase 6 final local results follow; earlier counts remain historical in their phase reports. No PostgreSQL gate is substituted with SQLite or a redirect mock.

- PostgreSQL 18, `seva_0006`, **30 tables**, full migration downgrade/reapply and drift:
  PASS. Recovery control and worker heartbeat are separate from cleanup health.
- Final full backend gate: **642 passed**, two existing FastAPI/Starlette test deprecation
  warnings, 49.55s, including the final paid-context correction.
  New coverage includes readiness/triage, 50 generated API operations, withdrawal media,
  empty bootstrap, actual PG restart/custom-archive restore into a separate DB, post-backup
  erasures/expiry, session/grant/lease invalidation, corrupt/incomplete/stale manifests,
  failed object purge retaining quarantine, and small acceptance observations.
- Paid-context correction subset: **19 passed**, 5.34s; accepted owned/routed case,
  stored coordinates, spoof/cross-owner denial, quota before calls and post-IO withdrawal.
- Ruff check/format: PASS, **146 files**.
- Signed SDK/session/BFF/Python identity checks: **5 passed**, zero skips.
- Development resident browser suite: **5 passed**, 23.4s, including expiry clearing;
  reviewer suite: **2 passed**, 39.6s, including queue expiry and current role revocation.
- HTTPS production-build pilot: resident **5 passed**, 12.4s; authority **2 passed**, 23.6s.
  Real local SDK/secure host-only cookie/BFF/TLS API, separate worker/cleanup fixture;
  signed synthetic OIDC, held initial queue/zero synthetic retry waits, no production bypass.
  Saved-context request-shape correction is included. Maps disabled at build time and
  nonlocal browser requests refused. Hydration input-loss correction is included.
- Existing legacy Chromium suite: **62 passed**, 1.2m, security-patched standalone build.
- Frontend lint/typecheck/build and OpenAPI/frontend type generation: PASS; generated
  drift/protected-record/link checks pass. Secret scan: **3,210 files / zero findings**,
  including the build. All 11 protected records, four baseline hashes and 15 document
  link sets pass; `git diff --check` passes.
- Runtime advisories: Python **61 pins / zero reported advisories**; production frontend
  **zero reported advisories** after targeted security fixes. Full development audit still
  reports **7 moderate nodes of one minimatch/TypeScript ESLint issue**, with no high or
  critical finding. This is documented unresolved tooling exposure, not a full-audit pass.
- Exploratory set integrity: PASS, **12 synthetic scenarios**, split **8 development /
  4 reserved**. **0 field cases, 0 real participants, 0 proxies, 0 walkthroughs**.
  Protocol/empty CSV prepared; recruitment/domain review/field sourcing are external.
- Actual six-request sequential synthetic acceptance and one small archive/replay timing
  observations are recorded under evidence/phase6. They establish no production capacity,
  hosting cost, human benefit or incident accuracy.

No live backend provider, historical research/training/final-evaluation run, remote CI,
hosted pilot, recruited reviewer or government receipt is claimed. An initial discarded
browser run exposed old compiled Maps configuration; final rehearsal explicitly disabled
Maps and blocked nonlocal traffic. Temporary API/web servers were stopped and the
phase-specific disposable PostgreSQL container was removed after verification.
MODEL_NOT_ACCEPTED and protected historical scientific records remain unchanged.

## Verification commands

Run database-mutating suites serially against the guarded disposable local PostgreSQL
setup in [DEVELOPMENT.md](../DEVELOPMENT.md), with `TEST_DATABASE_URL` and
`SEVA_TEST_PG_CONTAINER` set. These commands were exercised; results are above:

- API directory: `.venv/bin/python -m pytest -q`, `.venv/bin/ruff check .`,
  `.venv/bin/ruff format --check .`, `.venv/bin/python scripts/export_openapi.py`.
- Web directory: `npm run test:identity`, `npm run test:resident`,
  `npm run test:authority`, `npm run test:pilot`, `npm run test:e2e`,
  `npm run generate:api`, `npm run lint`, `npm run typecheck`, `npm run build`.
- Root: `python3 scripts/scan_secrets.py --include-build`, `git diff --check`.
- Advisory records: locked-runtime `pip-audit`, `npm audit --omit=dev --json`,
  `npm audit --json`; the full development audit has the unresolved finding above.

The final regeneration reproduced OpenAPI/frontend types unchanged. Hash/link/split
checks verified 11 protected records, four baseline files, 15 document link sets and
8/4 disjoint synthetic case IDs. The synthetic test container is no longer running;
recreate it to repeat the PostgreSQL suites. The machine-readable handoff is
[PILOT_RELEASE_CHECKLIST.json](PILOT_RELEASE_CHECKLIST.json).

## Limits and next dependency

Live Auth0 sign-in/refresh/back-channel, private R2 checks, hosted database roles/
migration/backups, separate continuous worker, scheduled physical cleanup/deletion-ledger restore, source/
billing permitted use and approved notices remain external release gates. Runtime dependency advisories found in this phase were patched. The development-only
moderate minimatch advisory remains tracked; no zero-vulnerability claim.
Case-detail panels are bounded snapshots; only audit history has full UI pagination.
Exports are bounded metadata copies, not complete case/provider-content packets.
Resident privacy-management UI remains outside this phase. No real field visits,
recruited participants, measured benefit, government partnership or agency receipt.

Phase 7 local release checks below are complete. No new phase, deployment, recruitment
or model work is automatically authorised.

## Phase 7 — current local release checks

Base `6f071afd10f0ffed024448ac87d3bfae9ec8abc4`, branch `codex/seva-phase-7`.
[Direction](DESIGN_DIRECTION.md), [implementation report](PHASE_7_POLISH.md),
[before/after gallery](screenshots/phase7/README.md).

The pilot public home, account shells, resident form/receipt/history/replies and authority
queue/evidence/actions now use a shared scoped light system and self-hosted Geist. The
prototype presentation is preserved. No API/scientific/access contract or live deployment
changed. Field enums, revision semantics, private/internal projection, source quotas and
retention remain backend-owned. Necessary UI fixes cover queue hydration, source-request
loading, empty map height and cold-route sign-in spacing. No architecture expansion.

- Full actual-PG backend: **642 passed**, 54.05s, two existing deprecation warnings.
- Signed identity/session checks: **5 passed**, zero skips.
- Baseline before design: resident **5 passed**, 29.0s; reviewer **2 passed**, 36.7s.
- Development design verification: resident **7 passed**, 48.3s; reviewer **2 passed**,
  48.6s before the final copy/spacing adjustment. Final HTTPS checks supersede those
  intermediate screenshots. Exact-row/committed-response revocation development recheck:
  **2 passed**, 46.7s (41.4s full journey + 4.3s administration).
- Final production-build HTTPS pilot: **7 resident passed**, 25.5s, **2 reviewer/admin
  passed**, 36.3s, with exact-row committed-revocation checks and stable-scroll captures.
- Final complete legacy Chromium regression: **62 passed**, 1.1m.
- Ruff check/format: PASS, 146 files. Frontend lint/typecheck: PASS. Production build: PASS.
- Generated OpenAPI, frontend types and legacy receiver schema reproduce unchanged.
- Rendered axe-core 4.13.0: **32 view/viewport records**, zero violations/incomplete checks.
  Keyboard/focus, 320px/200% form text reflow, reduced motion and map/GPS fallback tested.
  This is bounded Chromium verification, not a full WCAG/device/screen-reader audit.
- Screenshots: **18 before / 30 after** actual local synthetic images, 390px and 1440px;
  final after captures come from the HTTPS run. 48 PNG hashes and 175 selected source/asset
  fingerprints are recorded; screenshots wait for scroll position zero before capture.
- New browser checks assert empty history/queue, loading, safe unavailable/session errors,
  zero paid-source calls on navigation/resize, retry/expiry and stale revisions. Complete
  information request → resident reply → follow-up → reasoned closure → separate reporter
  publication/export and current membership suspension remain covered.
- Revocation-test correction: the broad old text regex could combine two list rows and
  race the suspend response. An isolated DOM reproduction returned one false broad match
  while the target remained ACTIVE. The exact row matcher returned zero. The test now
  checks the signed principal, committed DB row and completed mutation before immediate
  denial; no backend auth change was required. The old logo-first keyboard check now
  verifies skip link → logo plus Enter-to-main. No substantive test was dropped.
- Secret scan including final build: **3,460 files / zero findings**. 18 document link sets,
  11 protected records, four baseline hashes, original references and evaluation split pass.
  Generated OpenAPI/types/receiver schema reproduce unchanged; `git diff --check` passes.
- Fresh production frontend audit: zero advisories. Full development audit retains the
  known **7 moderate dependency nodes of one minimatch issue**; no high/critical. This
  remains documented tooling exposure. No Python dependency changed in Phase 7.

Commands: API `.venv/bin/python -m pytest -q` with guarded TEST_DATABASE_URL and
SEVA_TEST_PG_CONTAINER, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`,
`.venv/bin/python scripts/export_openapi.py`; web `npm run test:identity`,
`npm run test:resident` / `tsx tests/resident/run.mts --all`, `npm run test:authority`,
`npm run test:pilot`, `npm run test:e2e`, `npm run lint`, `npm run typecheck`,
`npm run generate:api`; `test:pilot` invokes `npm run build`. Root secret scan includes
build output; hash/link/case-split checks and `git diff --check` finish the handoff.
Advisory JSON lives under evidence/phase7; full dev audit returns a nonzero exit as above.

Remaining dependencies are the live/private-pilot gates in the runbook and release
checklist, including domain/reviewer feedback and device/assistive-technology review.
No Hindi translation review, participant evidence, field benchmark or benefit/accuracy
measurement is claimed. No new phase is started; the next action is an owner-reviewed
local release/private-pilot configuration when authorised, not automatic public deployment.

Temporary prototype API/web services were stopped. The disposable Phase 7 PostgreSQL
container and capture-inspection scratch files were removed after the final checks.
No commit, push, deployment, production data mutation or outreach occurred.

## Deployment preparation — 11 November 2026

The no-publication statement above records the Phase 7 handoff. The user subsequently
authorised GitHub publication and deployment preparation. Commits 2121566, 5198f0f and
e86abac are published on codex/seva-phase-7; main remains 142dfc1. GitHub's four jobs passed
for e86abac. The user confirmed the lowercase-pilot Vercel preview renders the new homepage.
This does not establish a functioning hosted resident/reviewer journey.

Deployment follow-up adds a checked transactional offline hosted migration command and a
separate cleanup-role script with actual PostgreSQL privilege/retention coverage. No Neon
migration or paid service was created. Follow-up backend: **657 passed**, 51.91s; Ruff check/
format PASS (148 files), secret scan PASS (693 files), diff whitespace PASS. The 15 added
tests cover checked migration targets/transactions/concurrency and restricted cleanup roles.
Signed SDK/session/BFF/Python identity: 5 passed, zero skips; generated contracts unchanged.
User-confirmed configuration: Neon production branch empty; Auth0 app now created, tenant/API
configuration still pending; no Render worker/cron. The owner selected preview only and no
paid hosting for now. See DEPLOYMENT_STATUS.md,
PILOT_RUNBOOK.md and RENDER_PILOT_PLAN.md for exact next dependencies and current evidence.
