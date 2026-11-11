# Phase 7 — actual before and after screens

All screens show local synthetic fixture records. Before: Phase 6 working tree, 11 November 2026.
After: Phase 7 HTTPS production-build rehearsal, same base HEAD with uncommitted UI changes.
390px mobile and 1440px desktop; not real pilot data or a same-case outcome comparison.

The original design references are separate from these running-product captures.
See [Phase 7 report](../../PHASE_7_POLISH.md) and [capture fingerprints](../../evidence/phase7/capture-manifest.json).

## Paired views

| View | Mobile before | Mobile after | Desktop before | Desktop after |
|---|---|---|---|---|
| authority partial | [Before](before/authority-partial-mobile.png) | [After](after/authority-partial-mobile.png) | [Before](before/authority-partial-desktop.png) | [After](after/authority-partial-desktop.png) |
| authority queue map fallback | [Before](before/authority-queue-map-fallback-mobile.png) | [After](after/authority-queue-map-fallback-mobile.png) | [Before](before/authority-queue-map-fallback-desktop.png) | [After](after/authority-queue-map-fallback-desktop.png) |
| authority reviewed | [Before](before/authority-reviewed-mobile.png) | [After](after/authority-reviewed-mobile.png) | [Before](before/authority-reviewed-desktop.png) | [After](after/authority-reviewed-desktop.png) |
| landing | [Before](before/landing-mobile.png) | [After](after/landing-mobile.png) | [Before](before/landing-desktop.png) | [After](after/landing-desktop.png) |
| resident failure | [Before](before/resident-failure-mobile.png) | [After](after/resident-failure-mobile.png) | [Before](before/resident-failure-desktop.png) | [After](after/resident-failure-desktop.png) |
| resident form | [Before](before/resident-form-mobile.png) | [After](after/resident-form-mobile.png) | [Before](before/resident-form-desktop.png) | [After](after/resident-form-desktop.png) |
| resident receipt | [Before](before/resident-receipt-mobile.png) | [After](after/resident-receipt-mobile.png) | [Before](before/resident-receipt-desktop.png) | [After](after/resident-receipt-desktop.png) |
| resident reply request | [Before](before/resident-reply-request-mobile.png) | [After](after/resident-reply-request-mobile.png) | [Before](before/resident-reply-request-desktop.png) | [After](after/resident-reply-request-desktop.png) |
| sign in | [Before](before/sign-in-mobile.png) | [After](after/sign-in-mobile.png) | [Before](before/sign-in-desktop.png) | [After](after/sign-in-desktop.png) |

## Additional failure and task states

| View | Mobile | Desktop |
|---|---|---|
| authority empty queue | [View](after/authority-empty-queue-mobile.png) | [View](after/authority-empty-queue-desktop.png) |
| authority revision conflict | [View](after/authority-revision-conflict-mobile.png) | [View](after/authority-revision-conflict-desktop.png) |
| resident empty | [View](after/resident-empty-mobile.png) | [View](after/resident-empty-desktop.png) |
| resident partial synthetic state | [View](after/resident-partial-synthetic-state-mobile.png) | [View](after/resident-partial-synthetic-state-desktop.png) |
| resident session expired | [View](after/resident-session-expired-mobile.png) | [View](after/resident-session-expired-desktop.png) |
| resident unavailable | [View](after/resident-unavailable-mobile.png) | [View](after/resident-unavailable-desktop.png) |

`resident-partial-synthetic-state` changes only the processing response state through a test-only
browser intercept of an actual accepted synthetic report. It demonstrates the label, not a provider result.
`authority-partial` shows actual synthetic timeout/unavailable providers, with human review still usable.
Rendered captions identify fictional records; no live sensor, government or accuracy claim is made.
The visually inspected screenshots remain full-page originals. Source and PNG SHA-256 values
are consistency fingerprints, not legal authenticity or deletion guarantees.
