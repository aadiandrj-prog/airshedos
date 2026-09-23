# Phase 3C — finalization verification

Verified locally on **23 September 2026 IST** (captures on 22 September UTC). Scope is demo reliability, claim clarity, receiver validation and deployment preparation. No major capability or post-3C work was added. Phase 2D remains **MODEL_NOT_ACCEPTED**; no custom model is deployed or retuned, and the locked test set was not opened.

## Baseline and protected records

With explicit user authorization, PR #9 was merged after its final-head checks passed. Work began on `codex/phase-3c-finalization` from clean merged main **1269055e8fcb6df861f6269416d4a8091f1acdb9**. Main's [CI run](https://github.com/aadiandrj-prog/airshedos/actions/runs/35712662733) passed. Baseline review/handoff smoke: **74 passed, 2 warnings, 1.76 s**.

`docs/contracts/protected-records.json` records SHA-256 for all ten preceding verification records (Phase 1A's `VERIFICATION.md` through 3B) plus `PREDICTION_MODEL.md`. **All 11 match both the manifest and merged 3B main byte-for-byte.** A regression test guards them. Historical statements in those records are intentionally preserved, not rewritten as current outcomes.

## Finalization changes and usability review

- One three-link **Demo journey** guides provider context → synthetic image/interpretation → officer review/handoff. It uses the existing boundary-area fixture and existing workflow.
- Explicit local labels distinguish Gemini AI interpretation, deterministic corroboration, illustrative legacy forecast and simulated handoff. Satellite-related waiting has explanatory copy; successful corroboration links back to the selected case.
- Mobile truth badges wrap within their panels instead of clipping. Existing dark-green layout, stacked mobile workflow, text map alternatives, keyboard controls and expandable provenance remain intact. Final desktop/mobile captures were inspected.
- No reset endpoint or saved interpretation is injected. The documented local API restart is the known-state reset: **all** ephemeral reports/cases/handoffs/demo actions and provider caches clear. Credentials, configuration, code and research artifacts are untouched. Reset before warming caches.
- Added a read-only preflight, standalone receiver example, generated JSON Schema, protected-record check, concise system overview, maintainable Mermaid source, practical demo checklist and deployment plan.

### Truth-label audit

| Area | Verified meaning |
|---|---|
| Current AQ, Weather, FIRMS, Sentinel-5P | Actual provider status, native units, observation/retrieval provenance; unavailable remains explicit |
| Citizen image | Generated synthetic fixture; real Gemini interpretation is tentative AI interpretation, not confirmed pollution |
| Corroboration | Deterministic rule support, reasons and limitations; forecast does not add an evidence vote |
| Google forecast | Google provider outlook, separate valid times and arithmetic trends; no AirshedOS-trained prediction claim |
| Legacy incident/forecast | Fictional/illustrative demo, including a label directly on its forecast card |
| Map/jurisdiction | Report/fire roles and text equivalents; prototype ownership can be Unknown; no official boundary or causality claim |
| Review/handoff | Temporary manual state, simulated recipient, no authority contact; visible independent expiry and integrity status |
| Research | Rejected custom model documented, never offered as a product prediction |

Queue labels, loading/disabled actions, no selected/new case, no fire, unavailable satellite/forecast/map, empty inbox, expired case and integrity mismatch retain understandable text. Provenance remains expandable, including provider/model identity, source-native units and distinct observation/retrieval/forecast-valid times. No private citizen material was used.

## Receiver-contract review

**PollutionEvent v1 is unchanged.** The review confirmed sender-scoped identifiers, event versions versus envelope revisions, UTC time roles, nullable/unavailable semantics, native units, explicit prototype jurisdiction/reason, frozen review state, Google forecast valid times and provenance references. Hash stays outside the payload; receivers hash exact exported bytes without reserializing. Python canonical encoding is documented and is not described as RFC 8785/JCS.

`docs/contracts/pollution_event_v1.schema.json` is generated from the backend serialization model with local `$defs`. CI checks regeneration and tests compare it with the model. `apps/api/scripts/receive_pollution_event.py` runs offline, imports no application code, verifies the sender's expected SHA-256, validates schema/version/required fields/aware timestamps and selected cross-field references, then prints a minimal summary. It rejects malformed/duplicate-key/non-finite JSON and bounds input at 2 MiB. It does not import, dispatch, establish authenticity or rerun scientific analysis. See [receiver semantics and limitations](INTEROPERABILITY.md#independent-receiver-review-phase-3c).

Both real rehearsal exports passed this validator in an isolated Python process. The second packet digest was:

```text
341ed47d804aca3c440d40e84d500c54dccc9e9a500d57c7d2c3f6a9180af74f
```

Evidence/case snapshot and forecast remained unchanged, the frozen payload stayed identical, audit history only appended, source/destination agreed, and handoff made **zero provider reruns**. Backend regression additionally installs fail-on-call provider fakes during handoff.

## Genuine final journey and latency

The same journey ran twice against local Docker with a real generated image submission, real Gemini, authenticated environmental providers, real Google Maps and real Google AQ forecast. HARYANA → DELHI was manually selected in the UI for the synthetic case at **28.52, 77.08**; prototype location ownership stayed **Unknown**. Both reached ACCEPTED, INTEGRITY VERIFIED, JSON download and independent validation.

These were browser-operated developer rehearsals using Playwright against real services, followed by visual review; timings are **automated interaction duration**, not a human's 3–5-minute narrated presentation. No live calls occur in CI. Both rehearsals needed **0 manual retries and 0 workarounds**; internal provider retry counts are not separately instrumented.

| Step | First rehearsal | Second/final rehearsal |
|---|---:|---:|
| Capture start UTC | 2026-09-22 22:47:18.757 | 2026-09-22 23:01:52.001 |
| Total journey | **12.872 s** | **11.388 s** |
| Browser/page/map ready | 2.886 s | 2.537 s |
| Gemini interpretation, wall time | 3.392 s | 3.332 s |
| Gemini provider time | 3.195 s | 3.084 s |
| Corroboration, wall time | 3.767 s | 2.612 s |
| Sentinel-5P inside corroboration | 3.672 s | 2.539 s |
| Google forecast lookup, genuinely cached | 1.95 ms | 2.49 ms |
| Packet generation through acceptance | 491 ms | 534 ms |
| Export, captures and independent validation | 2.100 s | 2.148 s |
| Separate cached-corroboration diagnostic | 27 ms | 33 ms |

The last row runs **after** the timed journey and can create another ephemeral assessment; reset before presenting. Page readiness includes browser launch/navigation. Export timing includes a 1.5-second tile-paint wait and screenshots, not just hashing. Values are single-run observations, not service-level guarantees.

Both journeys: Gemini interpreted; corroboration MODERATE; AQ/Weather/FIRMS CACHED from genuine preflight queries; satellite LIVE with NO2/CO/aerosol-index available; forecast CACHED. No provider was unavailable. Cache statuses remain visible and preserve original source times; nothing is substituted. Maps loaded at the correct report coordinate, desktop/mobile selection worked and neither capture had horizontal page overflow.

### Cold preparation and provider gates

After restarting the API, the first parallel live preflight took **13.668 s**: ground context 2.324 s, satellite 13.667 s and forecast 3.942 s. After the restart drill, the second preflight took **9.837 s**: ground 2.010 s, satellite 9.836 s and forecast 7.082 s. Both were PASS, with all providers LIVE. Satellite dominates cold preparation; the existing bounded timeout/loading copy is retained, and no QA threshold was changed.

Separate genuine **Gurugram 28.4595, 77.0266** gates also passed:

- AQ, Weather and FIRMS returned HTTP 200; cache reuse made no extra outbound calls and preserved source times. A deliberately disabled Weather adapter degraded independently.
- Earth Engine authenticated query PASS and cache PASS: 3 initial product queries, still 3 after reuse.
- Google forecast current AQ + 6/12/24-hour summaries PASS; CPCB available at all three horizons. One forecast and one current request, no additional requests after cache reuse (3.49 ms). This is integration verification, not forecast accuracy validation.

Sanitized local artifacts are gitignored under `data/verification/phase3c-*`: rehearsal reports, exact packets, desktop/mobile captures, both preflights, Gurugram environment/forecast gates and restart/missing-key drills. No HAR, raw credential-bearing console logs, access tokens or API keys are recorded.

## Failure drills

| Scenario | Method and observed result |
|---|---|
| Google AQ unavailable | New isolated mocked HTTP 503 test: AQ unavailable, Weather/FIRMS remain live |
| Google Weather unavailable | New isolated 503 test plus genuine gate's locally disabled adapter: other sources preserved |
| FIRMS unavailable | New isolated 503 test: null/unavailable remains distinct from a valid empty detection list |
| Sentinel unavailable/partial/timeout | Existing fixture tests: independent product states, bounded deadline and ground-context availability |
| Forecast unavailable/timeout | Existing backend/browser tests: explicit state, corroboration support unchanged |
| Gemini unavailable | Existing backend/browser failure/deadline tests: no fabricated interpretation; documented saved-material fallback is explicitly offline |
| Maps load failure | Mocked mobile browser workflow completes receive/accept using text and keyboard |
| Maps key missing | Separately compiled real frontend with empty browser key: bounded Map unavailable, 0 SDK requests, textual review usable, no mobile overflow |
| Integrity mismatch | Existing backend/browser tests block transitions/acceptance/export; standalone receiver rejects changed bytes |
| Source case expired | Controlled-clock backend and browser tests reject new work and show recovery text |
| Handoff outlives source | Controlled-clock backend test preserves independently frozen packet until its own TTL |
| Browser refresh | New browser regression reselects the sent packet; refresh does not acknowledge receipt or lose server state |
| Backend restart | Actual local Docker restart: 2 cases / 1 handoff → 0 / 0; old case/packet return 404; health/ready recover; prior exported file still independently validates |

The missing-key drill initially used port 3001, correctly rejected by existing CORS, and its first same-origin script skipped an asynchronous loading wait. The harness was corrected to wait for review controls and use the already allowed port 3000; **CORS/credentials/product behavior were not relaxed**. The normal Maps-enabled container was restored afterward. These separate diagnostic setup retries were not part of either successful timed journey.

## Regression and deployment status

| Check | Final local result |
|---|---|
| Full backend | **536 passed, 2 existing warnings, 24.29 s** |
| Full browser | **54 passed, 56.9 s**; mocked providers/Maps |
| Ruff | Check PASS; format PASS, 92 files already formatted |
| Frontend lint / typecheck / production build | PASS / PASS / PASS |
| OpenAPI / generated TypeScript / standalone schema | Regeneration byte-identical |
| Docker build/start/health | API and web healthy after final rebuild; separate restart drill PASS |
| Protected prior verification/model records | **11/11 unchanged**, also compared with merged main |
| Secret scan | **PASS: 1,876 source/build/artifact files, 0 findings**, including 10 sanitized Phase 3C JSON artifacts |
| Documentation links | **23 Markdown files checked, 0 missing local targets** |
| Phase 3C PR/CI | [PR #10](https://github.com/aadiandrj-prog/airshedos/pull/10); push and pull-request backend/frontend/browser/secrets checks are published on its exact head. Confirm those checks before merging; no auto-merge is authorized |

Preflight: `apps/api/.venv/bin/python apps/api/scripts/demo_preflight.py --live`. It reports PASS/WARN/FAIL for health, frontend/fixture, provider states, local configuration presence and Docker detectability without printing secrets or changing credentials. Configuration presence alone is not authentication proof. See [the demo checklist](DEMO_CHECKLIST.md).

Implementation commit: **0bb58572b2dbda45a20e96b494de1cca88fe395b** (`chore: finalize demo and reliability workflow`). Documentation-only follow-up completes the current architecture summary and PR references. The PR's checks remain the authoritative status for its latest revision; this verification record does not merge the branch.

**Public deployment is prepared, not provisioned.** The [deployment plan](DEPLOYMENT.md) provides environment separation, exact-origin CORS/Maps/HTTPS requirements, proposed Cloud Run/registry/secret-manager steps and health semantics. Read-only inventory found those three cloud APIs disabled. No billable infrastructure, IAM change, new credential or public release was created. Separate authorization is required before that plan runs.

## Remaining limits and stopping point

- Temporary single-process state, no accounts/user isolation/rate limits/durable audit. Unrestricted unattended public exposure is not recommended; a supervised deployment needs an approved exposure and quota plan.
- Provider/network latency and availability vary. Source acquisition and forecast-valid times differ; a snapshot can become stale. No new scientific or accuracy claims are made.
- Prototype jurisdiction ownership is not authoritative; handoffs remain simulated. SHA-256 checks integrity relative to a supplied digest, not authenticated sender identity.
- The offline receiver validates schema and selected cross-field consistency, not every nested scientific rule or truth of external claims.
- No public reset, hidden synthetic model output, persistent evaluation service or major feature was added. Existing local forecast snapshot tooling remains unchanged.

Recommended next work: **FINAL DECK / DEMO VIDEO / JUDGE Q&A PREP**, using the maintained [system overview](SYSTEM_OVERVIEW.md), [diagram source](architecture.mmd) and [single demo checklist](DEMO_CHECKLIST.md). Stop after Phase 3C; no next product phase begins automatically.
