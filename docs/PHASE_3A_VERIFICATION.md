# Phase 3A verification — spatial command center and officer review

Scope: Phase 3A only. No custom model, dispatch, alerts, accounts, database, cross-state federation, plume simulation or Phase 3B work.

## Git prerequisite and preservation

PRs #3 → #4 → #5 → #6 → #7 were merged in the authorized order. Each successor was updated against main and merged only after its updated CI passed. Clean main `c401c5aaa80f28c6ad053b98c7d378cfd5dbe94d` passed CI run [35107486914](https://github.com/aadiandrj-prog/airshedos/actions/runs/35107486914); its tree matched the verified Phase 2E head. Phase 3A began on `codex/phase-3a-command-center` from that main.

SHA-256 verification confirms all Phase 1B–2E verification documents and `docs/PREDICTION_MODEL.md` remain unchanged. Phase 2D remains **MODEL_NOT_ACCEPTED**. No custom model is deployed; no locked November–December test data was opened or model selection resumed. Existing prediction unit tests operate on synthetic fixtures only.

## Implemented

- Separate browser-key Google Maps JavaScript loader, accessible Advanced Markers and textual equivalents; bounded independent map failures.
- Three-area desktop queue/map/detail and stacked mobile workflow. Selected report/demo/probe plus returned FIRMS points only. No heatmaps or fake sensor markers.
- Maintained narrow prototype jurisdiction lookup for Gurugram/Haryana, central Delhi and Noida/UP; Unknown outside/ambiguous/edge areas. Explicitly non-authoritative, no routing.
- Process-local 64-case repository. Expiry capped by original report TTL; default 30 minutes, also lost on restart/eviction.
- NEW → UNDER_REVIEW → ACKNOWLEDGED/MONITORING/CLOSED_NO_ACTION, with documented continuation rules, revision conflict checks and no evidence mutation.
- Existing interpretation, deterministic corroboration, Google forecast and environmental components reused; provenance remains expandable. Forecast does not vote on corroboration.
- Explicit synthetic image intake, immutable input label and selected queue/map golden path.
- Developer-only prospective forecast snapshot/match CLI; gitignored local JSON, exact future observation matching, no polling or accuracy claims.

See [COMMAND_CENTER.md](COMMAND_CENTER.md) for API shapes, transitions, marker meanings, credentials, time semantics and demo steps.

## Maps credential verification

A separate browser key was created in project `airshedos`. Server AQ/Weather credentials were not reused. Verified server-side restrictions:

- Allowed API: Maps JavaScript API (`maps-backend.googleapis.com`) only.
- Allowed referrers: `http://localhost:3000/*`, `http://127.0.0.1:3000/*` only.
- Stored only in ignored root `.env`, mode 0600, under `NEXT_PUBLIC_GOOGLE_MAPS_BROWSER_KEY`.
- Intentionally compiled into browser assets; key value never printed in artifacts or documentation.
- Google `DEMO_MAP_ID` is used for this local prototype. Production map ID/origin setup remains future deployment work.

Live verification used an actual Chromium browser and real Google SDK/tiles, not the CI mock. Screenshots were visually inspected. It verified both approved origins, Gurugram (28.4595, 77.0266), marker rendering/selection and a 390×844 mobile viewport with no horizontal overflow. No Maps authentication/billing/API errors were reported. Only sanitized result fields and screenshots were retained under ignored `data/verification/phase3a-*`; no traces, HARs, credential-bearing network URLs or raw console logs.

## Live golden path

Gurugram synthetic input → real Vertex Gemini interpretation → real environmental corroboration → selected report map → Google forecast outlook → UNDER_REVIEW → MONITORING passed. The case remained explicitly synthetic; Gemini provenance and environmental live/cached states retained their own meanings. The forecast and all evidence were byte-for-byte equal before/after review; review revision reached 2. Prototype jurisdiction resolved to Haryana.

The initial full-path attempt exposed an omitted multipart allowlist entry for `is_synthetic`. This was corrected without changing image validation or inference behavior, covered by a backend regression, and the genuine path was rerun successfully. Genuine FIRMS zero detections were accepted; positive-fire marker selection is covered by the sanitized fixture browser test rather than manufactured live detections.

A real prospective forecast snapshot was recorded locally. Later observed-hour matching is intentionally not awaited; unit tests verify exact timestamp/location matching and rejection of past/misaligned observations. No accuracy evaluation was performed.

## Automated and container gates

| Gate | Result |
|---|---|
| Full backend tests | 456 passed; 3 existing dependency/platform warnings; 26.95 s |
| Full browser suite | 42 passed in 50.0 s; prior 31 plus 11 officer/map workflows |
| Python lint/format | Ruff check and format check pass |
| Frontend | ESLint, TypeScript and production build pass |
| OpenAPI/types | Exported from FastAPI and regenerated with openapi-typescript; consistency checked |
| Docker | API and web rebuilt, started and healthy with ADC and separated browser-key configuration |
| Secrets | PASS: 1,809 source/build/artifact files, 0 findings; backend credentials absent from compiled frontend |
| Prior verification records | All eight protected document checksums unchanged |
| GitHub CI | Implementation commit 224b1fc passed [PR CI](https://github.com/aadiandrj-prog/airshedos/actions/runs/35154879356); current head checks are linked from [PR #8](https://github.com/aadiandrj-prog/airshedos/pull/8/checks) |

CI uses fixture providers and a Google SDK mock, with Maps networking blocked. It never receives live provider credentials. Browser coverage includes queue/case selection; report and fire marker/text selection; no-fire centering; review and monitoring/closure; immutable evidence/forecast; synthetic intake-to-monitoring; map authentication/import failure; keyboard selection; expiry errors; mobile layout; and preserved fictional labeling. Backend coverage includes jurisdiction/unknown/overlap, lifecycle/invalid transitions/revisions, deep-copy immutability, expiry/capacity/ordering, HTTP serialization, no provider reruns, synthetic label persistence, prospective snapshot matching and narrow public-key scanner rules.

## Limits and next phase

Prototype jurisdiction rectangles are not official polygons. Cases and review history are ephemeral, with no accounts, identities or durable audit log. The map caps displayed fire points at 50 while all returned coordinates remain textual. Google Maps needs network/billing and the configured local origin. Only the selected workflow is mapped; standalone provider probe data does not pretend to be a physical sensor. No prospective forecast accuracy has been established. Optional forecast charts and officer notes were omitted to keep this phase narrow.

Focused [PR #8](https://github.com/aadiandrj-prog/airshedos/pull/8) remains open and unmerged. Implementation commit: `224b1fc7b8e3f8c2733878c6085d51e3ab9af4bb`. This follow-up records CI results only; no implementation changed.

Recommend scoping Phase 3B as **explicitly authorized jurisdiction handoff design**, with clear authority ownership, verified boundaries and a durable audit/identity plan before real routing. No Phase 3B implementation or automatic merge is authorized here.


## Final local live capture

Capture started **2026-09-16 21:51:43 UTC (17 September 03:21:43 IST)**. Both Google map tiles and marker/panel selection passed: localhost 2,691 ms; 127.0.0.1 2,052 ms (page navigation through marker selection, not SDK-only latency). Mobile overflow check passed. Gemini returned `interpreted` in 2,860.04 ms. AQ, weather, FIRMS and Google forecast reused valid provider caches. FIRMS returned 0 detections; corroboration was WEAK before and after officer review. The synthetic case resolved to prototype Haryana and reached MONITORING at revision 2 with its full evidence/forecast snapshot unchanged. This is integration verification, not source causality or forecast accuracy evidence.
