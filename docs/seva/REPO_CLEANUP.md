# Repository cleanup and production promotion — completed

11 November 2026. The owner requested cleanup, removal of old event branding and merging
codex/seva-phase-7 to main, and asked about a .tech domain. This authorises the merge;
paid hosting/domain purchases remain unauthorised.

## Prepared changes

- Replaced the obsolete no-accounts/in-memory README with the current resident/reviewer
  platform, deployed schema and honest remaining sign-in/worker/private-media limits.
- Archived seven superseded prototype/verification documents and the retired root Render
  Blueprint under docs/archive/prototype. Rewrote root hosting guidance and repaired
  relative Markdown links. The 11 integrity-protected records remain byte-for-byte at their original paths; scientific provenance, rejection records and exports are retained.
- Removed the old event-name checkout references from tracked documentation. The local
  workspace directory itself is preserved. No Git history was rewritten.
- Excluded local presentation/output scratch artifacts narrowly in .gitignore; no user
  artifact was deleted or published.
- Added server-side identity diagnostics reporting missing variable names or static error
  codes only. Exceptions, credential values and database URLs are omitted. Missing API
  audience now remains an explicitly unconfigured state. Public access still fails closed.

## Verification

Frontend lint, typecheck and production build passed. Actual local PostgreSQL signed
identity suite: 6 passed, zero skips. Prepared private frontend settings validate locally;
this does not establish which variables Vercel actually supplies. Markdown link check:
zero missing file targets; tracked Markdown event-branding check: zero matches. Secret
scan: pass. Source scientific/model acceptance logic is unchanged; no model research or
paid provider call was run. Full remote regression checks run on the published change.

## Remaining transition gates

Pause automatic deployment on the old Render airshedos-api before main changes; its
retired provider configuration conflicts with the new isolated prototype. Production
Vercel variables need independent configuration with APP_BASE_URL=https://airshedos.vercel.app
and the pilot API, and exact production Auth0 callback/logout/web origins. The actual
hosted sign-in failure remains under diagnosis. Worker/cleanup and reviewer provisioning
are separate remaining requirements for the controlled demo.

The clean airshedos.vercel.app production domain can serve the merged version. A registered
.tech domain can be added later through Vercel and exact Auth0 origins, after the owner
provides its name. No redemption code, purchase or DNS modification is requested here.
Do not delete the phase branch while preview/API services still depend on it.

The first remote backend run caught missing protected-record paths after archiving. Those
11 records were restored exactly without changing the manifest or weakening tests. The
19 finalisation/contract regressions now pass locally; full remote checks are rerun.
The owner confirmed the old Render API Auto-Deploy is off. Preview SESSION_DATABASE_URL
was found scoped only to Production; the owner corrected Preview scope and redeployed.
Hosted sign-in still needs confirmation. The .tech domain is not yet redeemed.

## Completed promotion

Owner confirmed the sign-in scope correction worked and Production/Auth0 settings were
saved. Both full corrected CI runs passed on 05e08af. PR #15 merged at 12:14 UTC as a5ead73.
Vercel Production succeeded; the clean URL serves the new homepage and secure sign-in.
A public login-start check returned 307 to the expected Auth0 tenant with the exact
production callback and audience; anonymous BFF and report-list reads returned 401.
Fourteen fully merged obsolete remote branches were removed, retaining main and the
phase-7 branch while preview/API still depend on it. The local checkout is now on main;
ignored user artifacts and private credentials are preserved. No history rewrite occurred.
A registered .tech domain can be connected later; the current domain has not been redeemed.
Reviewer setup, worker/cleanup and production end-to-end rehearsal remain pending.
