# Phase 3B verification — simulated jurisdiction handoff

## Scope and baseline

Phase 3B adds PollutionEvent v1 and a manual simulated cross-jurisdiction workflow only. Phase 3A [PR #8](https://github.com/aadiandrj-prog/airshedos/pull/8) was merged with green checks at `d70862848635bd3e29bec1a8e50b5a4c6cf8ed43`; [main CI passed](https://github.com/aadiandrj-prog/airshedos/actions/runs/35679114031). Work began from that clean main on `codex/phase-3b-jurisdiction-handoff`.

Phase 2D remains **MODEL_NOT_ACCEPTED**. No model deployment, renewed model search or locked test evaluation occurred. Nine prior phase-verification/model documents were compared byte-for-byte with the merged baseline and remain unchanged. No Phase 3C work or real authority dispatch occurred.

## Implementation

- Required `pollution_event_v1` schema, typed normalized evidence/provenance, native units and explicit source/destination. No raw media, citizen free text, credentials or internal provider dumps.
- Frozen versioned payload, exact canonical UTF-8 JSON and SHA-256 envelope; integrity recomputed on reads/advancement/export. Mismatch blocks acceptance and all other transitions.
- Revision-checked DRAFT → READY → SENT_SIMULATED → RECEIVED → ACCEPTED / REJECTED / RETURNED_FOR_REVIEW. Returned packets can be readied/resend with unchanged bytes and appended audit.
- Source and destination views share one bounded process-local record. Generic actors, 128-entry append-only audit cap, 128-packet capacity and independent one-hour TTL. No authenticated/durable audit claim.
- Explicit Delhi/Haryana/Uttar Pradesh recipients; existing non-authoritative lookup retained, including Unknown at the fictional border-area point. No automatic routing/proximity inference.
- Existing command center gains a composer, prototype inbox, review panel and JSON export. Incoming selection maps the frozen report coordinate; keyboard/mobile/text fallback remain available.
- Focused create/list/detail/transition/export API. All pre-existing OpenAPI paths and component schemas were compared structurally and are unchanged. The regenerated contract remains the frontend type source.

Full field semantics, routes, versioning/canonicalization, boundary source limitations, expiry and deferred production requirements are in [INTEROPERABILITY.md](INTEROPERABILITY.md).

## Automated verification

Final local results on 22 September 2026:

| Check | Exact result |
|---|---|
| Full backend: `.venv/bin/pytest -q` from `apps/api` | **517 passed, 3 warnings, 28.33s** |
| Handoff coverage within backend suite | **61 tests**, including the complete 7×7 transition matrix, required/future/malformed schema, canonical round-trip, hash mismatch, versions, revision conflicts, immutable source/forecast/audit, expiry/eviction/order, unsupported jurisdiction, partial sources and HTTP no-provider-rerun guard |
| Ruff check / format | **PASS**; 89 Python files already formatted |
| Full Chromium browser suite against rebuilt Docker | **52 passed, 58.2s**; 42 prior tests plus 10 handoff tests |
| Frontend lint | **PASS** |
| Frontend typecheck | **PASS** |
| Frontend production build | **PASS**; static `/` and `/_not-found` |
| OpenAPI and TypeScript regeneration | **PASS**, unchanged hashes after regeneration |
| Existing API compatibility | **PASS**; zero removed/changed prior schemas or endpoint definitions |
| Docker build/start/health | **PASS**, API and web healthy using existing ADC override |
| Secret scan: source + compiled frontend + sanitized manual JSON/export | **PASS**, 1,839 files, 0 findings |
| Prior verification/model documents | **PASS**, 9 unchanged baseline files |

Backend warnings are pre-existing framework deprecation notices and the local joblib physical-core fallback; there are no failed/skipped phase gates. CI runs injected provider fakes, sanitized fixtures and mocked Maps only. No live diagnostic script is wired into CI.

Browser coverage includes explicit origin/destination/reason, frozen preview, send/inbox/receive/accept, reject/return, invalid transition recovery, hash-mismatch acceptance/export blocking, tampered downloaded bytes, exact canonical export, synthetic intake labels, incoming marker, keyboard/mobile flow with Maps unavailable, unchanged assessment/provider request counts, and protection against a delayed incoming response overriding a newly selected source workflow.

## Authenticated synthetic manual gate

Capture started **2026-09-22 09:11:34.777 UTC (14:41:34.777 IST)** against the rebuilt local Docker services. Ran `node apps/web/scripts/verify-handoff.mjs`. This uses an explicitly synthetic image and genuine configured interpretation/environmental providers, then performs the transfer entirely inside the prototype.

| Gate | Observed result |
|---|---|
| Scenario | Fictional border-area input at **28.52, 77.08**; location ownership **Unknown**, non-authoritative |
| Gemini | `interpreted`; synthetic input flag retained |
| Scientific assessment | **MODERATE**, unchanged by handoff |
| Forecast | Google provider **live**; 6h STABLE, 12h STABLE, 24h WORSENING; separate from support |
| Manual recipient choice | **HARYANA → DELHI**, `CROSS_BORDER_EVENT`; prototype control rooms only |
| Handoff ID | `HO-b2292b33-8cd4-4c78-a6ee-a72e064f1b6a` |
| Lifecycle | DRAFT → READY → SENT_SIMULATED → RECEIVED → **ACCEPTED** |
| Version / revision | Event version **1**, final handoff revision **4** |
| Integrity | **VERIFIED**, exported bytes independently SHA-256 checked |
| SHA-256 | `e4318b95e5bdfa9208eaf4f166207cb48795557381be19571151a262f75a6020` |
| Audit | **5 entries**, prior sent audit remains an exact prefix; generic source/destination actors |
| Source/destination consistency | Both lists report ACCEPTED for the same packet |
| Evidence / forecast / provenance | Entire source case and entire frozen packet unchanged before/after |
| Provider reruns during handoff | **0**; receiving/acting/exporting did not rerun Gemini or environmental/forecast requests |
| Map | Google map loaded; actual Advanced Marker identified SIMULATED HANDOFF REPORT at **28.52, 77.08** |
| Mobile | 390×844 viewport, no horizontal overflow; desktop/mobile screenshots visually reviewed |
| External authority dispatch | **None**; handoff code has no remote transport/provider dependency |
| Overall manual gate | **PASS** |

Sanitized artifacts are deliberately gitignored: `data/verification/phase3b-manual.json`, `phase3b-pollution-event.json`, `phase3b-desktop.png`, `phase3b-mobile.png`. No HAR, raw console/network URLs, credentials or media bytes are included in the JSON export/results. Screenshots show the simulated/prototype and synthetic labels, text location, separate Google outlook and integrity status. The map imagery is supporting context, not authoritative jurisdiction resolution.

The no-rerun guard is tested independently at the backend: after source corroboration, Gemini analyze, environment context and forecast entry points are replaced with functions that fail if invoked; the complete handoff lifecycle still succeeds. This supplements the manual browser request counters. Frozen packet/provenance equality is checked directly, not inferred from a matching support label.

## Known limitations and deliberate deferrals

Import, optional notes, automatic proximity suggestions and official boundary ingestion are deferred. Jurisdiction lookup uses clearly marked interior prototype rectangles; no exact state ownership is inferred. Origin/destination are manually chosen workflow labels. Event versions are process-wide and may have per-case gaps. SHA-256 verifies content integrity against the expected digest, not authenticity or non-repudiation; canonical v1 encoding is not RFC 8785/JCS. Receivers hash exported bytes without reserialization.

State/audit are ephemeral, single-process and bounded; restart/TTL/eviction removes them. Browser copies can remain visible until refreshed. No accounts, authorization, remote delivery, persistent database, official agency registry or delivery guarantees exist. Forecast and environmental snapshots can become stale because destination receipt never refreshes them. Source-case expiry does not prematurely delete an existing handoff. Real integration requires the separately documented production requirements and agreements.

Recommend Phase 3C/finalization begin with a scoped demo/usability and receiver-contract review. Do not infer authorization for real routing, identity/persistence infrastructure or new modelling. **Stop after Phase 3B.**

## GitHub review

Focused [PR #9](https://github.com/aadiandrj-prog/airshedos/pull/9) is open and unmerged. Implementation commit: `3cc113b9b554adcfb98d7740a7ac8fe2acba4409`.

All eight implementation checks passed: backend, frontend, browser/Docker and secrets on both the [push run](https://github.com/aadiandrj-prog/airshedos/actions/runs/35709300302) and [PR run](https://github.com/aadiandrj-prog/airshedos/actions/runs/35709341517). This documentation-only follow-up records those completed results. The [PR checks](https://github.com/aadiandrj-prog/airshedos/pull/9/checks) show the current head's verification. No automatic merge is authorized.
