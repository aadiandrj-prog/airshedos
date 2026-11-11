# Phase 7 — UI design and polish

11 November 2026, Asia/Kolkata. Local implementation, no live deployment.
Selected checkout: `/Users/aadityajain/Technical Assessments/Onboarding/Google Build Week`.
Base/HEAD: `6f071afd10f0ffed024448ac87d3bfae9ec8abc4`. Branch `codex/seva-phase-7`.
Prior uncommitted Phase 0–6 changes and unrelated presentation/output files are preserved.
No commit, push, paid provisioning, production migration, real-data collection or outreach.

## Direction and implementation

[DESIGN_DIRECTION.md](DESIGN_DIRECTION.md) records the chosen design, references and
adaptations. The user supplied a Phase 7 implementation request separately from the
Auralis/Stitch source material. The generated exports are references, not instructions
to import their scripts, features or claims. All three source images were inspected;
original HTML, DESIGN.md and PNGs are retained in [design-references](design-references).
The [reference manifest](evidence/phase7/reference-manifest.json) records their hashes.

The pilot home now has an editorial asymmetric hero, direct reporting/history/reviewer
entry points, a labelled synthetic timeline, two workspace paths and evidence limitations.
No invented sensor network, reading, station/partner count, activity chart, verification
percentage, legal badge, dispatch service or model feature was introduced. Pale atmosphere
is restricted to the preview; forms, decisions and evidence use opaque reading surfaces.

Resident screens share a light canvas, locally served Geist, readable 16px form controls,
numbered sections in a single form, secondary GPS/map actions and clear validation/retry.
Receipt, analysis and published review updates remain distinct. Requests for more
information appear before the original report, with a separate reply form. Own history,
submitted facts, unknown time, private photo retention and published timeline remain.
Sign-in, expired/unavailable states and sign-out have usable navigation and recovery.

The authority workspace uses a unit rail, scoped queue with explicit filters/counts,
list-equivalent map fallback, case status and section jump links. Wide case views place
report/evidence beside human actions; tablet and mobile reflow to one column. Internal
notes are explicitly unit-only, with **Add internal note** separate from **Publish update
to reporter**, including the existing preview. Assignment, review reasons, information
requests/replies, field follow-up, evidence versions, audit pagination and bounded manual
metadata export retain the original APIs, permissions and revision rules. Closure says
review ended; it makes no clean-air or legal finding. Reporter status text is humanised
without changing submitted enum values. AQ preserves each provider index name/code/category
and forecast stays a separate peak-window outlook.

Shared `.pilot-ui` tokens isolate this design from the existing synthetic prototype.
`APP_MODE=pilot` selects the new public home; prototype mode retains its original command
centre. This preserves the selected release boundary and old regression surfaces. The
running hosted site has not changed. No new backend API, schema migration, auth integration,
scientific rule, provider-retention policy or forecast model was added in this phase.

## Issues found and corrected

- Queue filters could receive input before hydration and lose the typed value. They now
  wait for the first client load; the test asserts the filtered count and matching case.
  This is a necessary UI correctness fix, not a permissions/backend scope expansion.
- Optional source context now disables its button while loading. Neither navigation,
  resizing nor ordinary rerenders trigger source work. The map fallback removes unused
  blank map height; manual coordinates and the permitted list stay usable.
- A fresh sign-in render lacked button spacing because its styles were in a resident-only
  stylesheet. Those rules now live in the shared shell stylesheet, with a geometry check.
- Decorative-gradient captions initially needed manual contrast review. Opaque caption
  surfaces remove the ambiguity; final rendered checks retain no incomplete results.
- A revocation assertion could match the whole membership list (target ID followed by
  another row’s SUSPENDED text), racing the pending suspension request. A small isolated
  DOM reproduction confirmed that false match. The strengthened test waits for the exact
  suspension response, checks the committed row and signed-in principal, and matches the
  target list item before asserting immediate access denial. No backend authorization
  change was needed; this was a test synchronization/specificity defect.
- An old keyboard assertion assumed the logo was the first focus target. It now checks
  the new skip link, the logo next, and keyboard transfer into main content. No
  substantive regression check was removed.

## Verification and evidence

The final command/results ledger is [PHASE_STATUS.md](PHASE_STATUS.md). Backend checks
use actual guarded disposable PostgreSQL 18, never SQLite or mocked permission queries.
The complete backend gate passed **642 tests in 54.05s**, including ownership/unit scope,
revocation, expiry/private media, quotas, fenced worker recovery and isolated restore.
Two existing FastAPI/Starlette dependency deprecations remain. No research training,
dataset extraction or historical scientific evaluation command was run.

Signed identity/session tests passed **5**, zero skips. The final production-build pilot passed **7 resident tests (25.5s)** and **2 reviewer/admin
tests (36.3s)**; **62 legacy Chromium regressions (1.1m)** also passed. Lint, types, build,
contract regeneration, protected hashes, 18 local document link sets and the secret scan
(**3,460 files / zero findings**, including build output) pass. The production-build pilot
rehearsal uses HTTPS, actual SDK/BFF session handling, Secure/HttpOnly host-only cookies,
separate API and worker, real PostgreSQL and explicit local signed synthetic OIDC.
Browser contexts refuse nonlocal traffic; Maps are disabled at build time. Test-only
worker timing remains controlled as described in the Phase 6 runbook, not a hosting
capacity measurement. The resident/reviewer journey verifies actual submission, lost
receipt recovery, optional-photo failure, review, private note, stale revision rejection,
information request, resident reply, field finding, reasoned closure, deliberate public
update, scoped export and immediate membership revocation. Source failures do not remove
the saved case. Existing legacy browser regressions are retained.

Rendered axe-core 4.13.0 checks cover WCAG 2.0/2.1 A/AA and 2.2 AA rule tags in Chromium.
The final evidence has **32 view/viewport checks**, zero violations and zero incomplete
checks. These are selected rendered states, not every interaction or full certification.
Keyboard tests cover skip navigation, native form order, visible focus, Enter activation
and logout. Reflow checks cover 390px and 1440px captures plus 320px, 200% text enlargement
on the form, reduced motion and a 44px submit target. No screen-reader, real mobile device,
Safari or Firefox review is claimed. [Contrast measurements](evidence/phase7/contrast.json):
body/white 17.85:1, secondary/canvas 7.24:1, link/white 5.93:1, focus/canvas 5.67:1 and
status-chip text 6.85:1. Rendered checks complement these token measurements.

[Before/after gallery](screenshots/phase7/README.md): **18 before / 30 after** real screenshots
of the local running application at 390px and 1440px. Before views were captured from the
Phase 6 worktree before visual changes; final after views come from the HTTPS production
rehearsal. Synthetic cases differ by run; the screenshots are not same-record outcome
comparisons or real field evidence. `resident-partial-synthetic-state` uses a test-only
intercept of the accepted report's processing state to exercise the PARTIAL label. The
`authority-partial` filename shows actual injected provider failures and their limitations;
it is not a successful-provider claim. Empty history/queue, failed save/map/GPS, unavailable
report, expired session, revision conflict and a reply request are also represented.
All displayed reports and private notes in these captures are synthetic fixture records.

The images were visually inspected at mobile/desktop sizes, including the form, receipt,
reply request, queue/map fallback, case columns, error states and public composition.
The capture helper waits for instant top-of-page scrolling to settle before taking each
final screenshot. The gallery and 175 selected source/asset plus 48 capture fingerprints make the uncommitted release reviewable;
HEAD alone is not a snapshot of this work. No user-study result is inferred from pixels.

## Limits and handoff

Production frontend dependency audit reports zero advisories. The full development audit
still reports the previously documented seven moderate dependency nodes from one minimatch
advisory. This unresolved development-tooling exposure remains tracked; it is not a
zero-vulnerability or full-audit pass. No unrelated dependency upgrade was introduced:
axe-core, already present transitively, is now pinned directly as a development test tool.
Geist is an installed local font asset with its SIL license retained.

The existing summary API contains receipts/dates/processing, not description previews or
last-publication text. History therefore links to the actual detail/timeline instead of
inventing summary fields or expanding the API for decoration. Detail panels/exports keep
the previously documented bounds. No Hindi strings were added without a pilot need and
translation review. No recruited reviewer, translation reviewer or accessibility expert
was available; there is no claimed user validation, measured benefit or incident accuracy.

[Release runbook](PILOT_RUNBOOK.md), [environment template](pilot.env.example) and
[release checklist](PILOT_RELEASE_CHECKLIST.json) still require the live Auth0/private
storage/hosted worker-cleanup/independent erasure-journal/backup checks, approved notices,
unit roster and provider terms/budgets before a private pilot. The local release has not
updated the deployed site. Public deployment, real-data collection, spending and messages
require separate authorization. Phase 7 ends at the polished verified local release;
there is no automatically started next phase or model programme.
