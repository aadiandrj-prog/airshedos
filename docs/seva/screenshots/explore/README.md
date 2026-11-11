# Area overview visual verification

Captured from the local production-build HTTPS browser harness. Values are synthetic
Google-shaped/FIRMS fixtures, intercepted only in Playwright, and marked in the capture.
They are not live measurements, recruited-user evidence or accuracy/capacity measurements.
The committed fixture is under apps/web/tests/fixtures/explore-synthetic.json.

- mobile-synthetic.png: 390px viewport, full result with source times and attribution.
- desktop-synthetic.png: 1440px viewport, same data and light platform design.

The browser test checks no horizontal overflow, axe violations, explicit-load-only requests,
area-switch cancellation, shared-limit messaging and removal of expired content without
an automatic paid refresh. Original Phase 7 visual captures retain their historical scope.
