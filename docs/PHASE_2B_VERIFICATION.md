# Phase 2B verification — transparent corroboration

Implementation and local/live verification completed on 13 September 2026. **No Phase 2C work.** The Phase 2A PR (#3) remains an open dependency pending merge authorization; this Phase 2B branch is based on its verified head `0e84cb0a1708323835cab6142801039b78c8617d`. It is not represented as merged main. The focused review targets the Phase 2A branch until that dependency can be merged and the review retargeted to main. Do not merge Phase 2B automatically.

## Implementation and rules

- `app/corroboration`: typed assessment, rule verdicts, source summary, explicit provenance, validated policy settings, ephemeral report repository, pure rules/aggregation, POST route.
- Successful analysis adds only a nullable `structured_report_ttl_seconds` response field and stores server-owned report metadata/interpretation/signal. Gemini's prompt, schema normalization and provider behavior remain unchanged.
- `POST /api/v1/citizen-reports/{report_id}/corroborate` accepts no body. It retrieves the report, independently queries environmental context and returns an assessment. Invalid/expired/evicted IDs return a clear 404 before network work. No image reupload or second Gemini call.
- Temporary storage: 256 entries, fixed 1,800-second TTL, deep copies, LRU eviction, idle-expiry timers, shutdown/restart reset. No image bytes or image URL; no disk persistence, database or assessment cache. The existing environment provider caches are reused.
- Families: COMBUSTION, DUST, ATMOSPHERIC_HAZE, TRAFFIC, NONE_OR_UNCERTAIN.
- Seven explicit rules: `CITIZEN.VISUAL.v1`, `AQ.CPCB.v1`, `FIRMS.PROXIMITY.v1`, `WEATHER.WIND.v1`, `SATELLITE.NO2.v1`, `SATELLITE.CO.v1`, `SATELLITE.AEROSOL_INDEX.v1`.
- CPCB <=100 neutral, >100–200 weak support, >200 support as regional particulate context; requires relevant particulate dominant code. DUST requires PM10. No UAQI or raw-concentration conversion.
- FIRMS combustion support requires nominal/high confidence: <=5km and <=6h strong rule; <=15km and <=24h weak rule; >15–25km regional context only. Zero detections are neutral.
- Wind uses the nearest eligible fire, from→transport +180°, spherical fire-to-report bearing, shortest angular difference <=45°, speed >=1m/s, fire/weather time gap <=1h. Conditional consistency only; no independent category increase.
- Satellite NO₂/CO remain `mol/m²`, UVAI dimensionless; all context-only. **Scientific QA thresholds and existing satellite provider code are unchanged.**
- Ages: AQ <=2h, weather <=1h, FIRMS <=24h (strong/wind <=6h), satellite <=24h for fresh context. Older observations remain explicit as stale; source lookup still uses the original 72h/10km satellite policy. More than 5 minutes future skew is excluded. Submission is a proxy; photo capture time is unknown.
- Aggregation: explicit visual-field disagreement → CONFLICTING/REVIEW; uncertain/unsupported visual or no applicable fresh environmental data → INSUFFICIENT; high visual + strong FIRMS → STRONG; positive visual + positive AQ/FIRMS → MODERATE; otherwise visual with neutral available context → WEAK. No-visible interpretation suggests no action from current evidence; other insufficient cases suggest review. Recommendations are advisory, with no demo incident mutation.

Full thresholds, exact applicability, configuration, conflict guard and limitations: [CORROBORATION_RULES.md](CORROBORATION_RULES.md). That document cites the official Google AQ, Weather, NASA FIRMS and Earth Engine semantics checked during implementation. The operational distance/age/aggregation bands are inspectable heuristics, not validated scientific cutoffs.

## Automated regression

| Check | Result |
| --- | --- |
| Full backend | **279 passed**, 2 upstream Starlette/AnyIO deprecation warnings; final local run 8.52s |
| New Phase 2B backend coverage | **64 tests** including boundaries, applicability, actual visual inconsistency, staleness/future skew, native units, provenance, wind cardinal/wrap/opposite/calm/time-gap/nearest-candidate cases, fixed TTL/capacity/copies/timer cleanup, invalid IDs, forged bodies, failed analysis, no second Gemini, no incident mutation, deterministic replay, text ignored and provider cache reuse |
| Prior backend regression | All **215** tests preserved and passing |
| Full Chromium browser | **26 passed** in 33.6s: previous 19 plus 7 Phase 2B flows |
| New browser flows | explicit analyze→corroborate/loading; strong card; moderate category; partial failure; insufficient/review; expired report; provenance expansion; clear during in-flight lookup (covered across 7 tests) |
| Python lint/format | Ruff check and format check passed |
| Frontend lint/typecheck | Passed |
| Frontend production build | Passed; Next.js static routes generated |
| OpenAPI/generated types | Re-export/regenerate is byte-identical; generated contract remains source of frontend types |
| Docker | Final API/web build/start and health checks passed, loopback ports; existing read-only backend ADC mount retained |
| Secrets | Build-inclusive scan passed: 1,677 files, zero findings |
| Diff review | No source-attribution or calibrated-probability output; no Phase 1 provider changes; no image persistence; no demo mutation; no Phase 2C implementation |
| GitHub CI | Published branch/PR checks are verified after push and reported in the completion report; CI uses no provider credentials or live scripts |

Network transports remain blocked by autouse fixtures in backend tests. Browser tests use synthetic routes; CI's default Compose has no cloud credentials. No live verification script is invoked by CI. The existing two dependency deprecation warnings are not test failures and were not hidden by weakening checks.

OpenAPI SHA-256: `81a1f49783bc89ec34380ddf056927b312625559acff1926dd97d12648c1198f`.
Generated TypeScript SHA-256: `8d8c827e9277a407c574155e9f0a77b85da3226eb84b6325c7dc3f39a1694e44`.

## Separate authenticated gates

[Gemini-only record](verification/phase2b-gemini-live.json): **PASS**, one real Vertex call with the existing synthetic open-burning image; `open_burning`, HIGH ordinal interpretation; 4,760.39ms wall latency. Uses existing backend ADC and `gemini-3.1-flash-lite`, with no new credentials or permissions.

[Environmental regression](verification/phase2b-environment-live.json): **PASS**, Google AQ, Google Weather, NOAA-20 FIRMS and authenticated Earth Engine all live. Three satellite products had usable observations under unchanged QA. Provider cache reuse, unchanged observation/provenance times and partial-provider failure all passed. Gurugram 28.4595, 77.0266; default satellite 72h lookback, 10km radius. No window or QA changes were used to force values.

## Full real transport gate

[Complete sanitized record](verification/phase2b-corroboration-live.json).

**Image-location pairing is synthetic; this verifies pipeline behavior, not event truth.** The image was generated for evaluation and was not captured at Gurugram. Neither the category below nor synthetic browser scenarios are scientific validation. No precision/recall/accuracy was calculated.

At **2026-09-13 06:48:28.730541 UTC**, the real synthetic-image → Gemini → environmental providers → deterministic engine sequence returned HTTP 200, **WEAK / MONITOR**. Gemini interpreted `open_burning` with HIGH ordinal visual confidence. That remains a tentative model interpretation.

| Evidence | Actual result | Rule verdict |
| --- | --- | --- |
| Citizen / Gemini | One real call; 4,389.17ms; photo capture time unknown | SUPPORTS |
| Google AQ | CPCB AQI **65**, dominant PM10; observed 2026-09-13 06:00:00 UTC; age 48.48min | NEUTRAL |
| NOAA-20 FIRMS | Two nominal detections, **21.727km** and **23.412km**, observed 2026-09-12 20:34:00 UTC; about 10.24h old | NEUTRAL; regional-only, beyond 15km |
| Google Weather | Observed 2026-09-13 06:48:18.386778 UTC; age 10.34s; no eligible nearby recent fire for alignment | NEUTRAL |
| Sentinel-5P NO₂ | **0.00005351062752739593 mol/m²**; QA usable; 4 candidates / 4 metadata-qualified | NEUTRAL/context-only |
| Sentinel-5P CO | **0.04325115046353522 mol/m²**; QA usable; 4 candidates / 4 metadata-qualified | NEUTRAL/context-only |
| Sentinel-5P UVAI | **−1.2593098568040946 dimensionless**; QA usable; 3 candidates / 3 metadata-qualified | NEUTRAL/context-only |

All three satellite observations were acquired **2026-09-12 07:51:10 UTC**; age **82,638.73s = 22.955h** at assessment. Each native unit, collection, band, complete Earth Engine image ID, applied QA and retrieval timestamp is retained in the JSON. Satellite calls took 9,307.84ms (NO₂, including initialization), 1,755.20ms (CO) and 612.05ms (UVAI). They are latest usable observations, not live satellite readings.

The full environmental/corroboration call took **11,684.32ms**. The repeated POST took **5.35ms**, with AQ, weather, FIRMS and satellite all CACHED and the category still WEAK. The manual gate confirmed **exactly one Gemini call**, deterministic replay of the same normalized input, and unchanged demo incident data. No provider failed in this full gate; partial failure is independently verified in the environment gate and automated tests.

## Frontend and review

The Evidence Fusion Card keeps the established dark-green editorial style. It shows the possible event, categorical corroboration, concise source rows, visible missing/stale evidence, advisory next step, limitations and expandable rule inputs/provenance. The selected FIRMS candidate's age is displayed when a candidate contributes; the full candidate list remains inspectable. Clearing or replacing a submission unmounts/aborts pending UI work. It cannot supply or edit the server-owned analysis.

Screenshots in `docs/screenshots/phase2b-fusion-desktop.png` and `phase2b-fusion-mobile.png` use explicitly synthetic browser-test evidence. They are UI verification, not live scientific results.

## Known limitations and deviations

- **Git baseline dependency:** Phase 2A PR #3 is verified but has not yet been authorized for merge in this phase. Work was isolated on `codex/phase-2b-corroboration` from that verified head; it must be reconciled with merged main before Phase 2B is merged. This is the outstanding deviation from “begin from merged Phase 2A main.”
- The CONFLICTING case is a direct inconsistency within structured visual output, not a invented physical contradiction between different footprints/times. No defensible cross-provider contradiction is inferred from the available evidence.
- AQ uses a conservative dominant-particulate policy; it cannot identify the source category. Wind and satellite do not independently increase the aggregate. STRONG requires the specific visual-plus-FIRMS policy.
- Source footprints and observation times differ; image capture time is unverified. Current service observations are not historical evidence about a photo. A missing or neutral source does not rule out an event.
- Process-local, bounded report storage is deliberately temporary. Capacity eviction/restart can end availability before TTL. Public access control, durable evidence custody and multi-worker storage are out of scope.
- No calibrated probability, forecasting, attribution, BigQuery, Maps, persistent database or operational dispatch was implemented.

**Recommended Phase 2C:** begin only after this review and explicit scope approval. Prioritize domain review of the checklist and a time/location-verified evaluation design before any predictive capability or calibrated scientific claim. No Phase 2C code or dataset construction has begun.

## Reproduction

Use existing backend credentials in the ignored `.env` and existing ADC. Run from the repository root:

```sh
apps/api/.venv/bin/python -m pytest apps/api/tests -q
apps/api/.venv/bin/ruff check apps/api
apps/api/.venv/bin/ruff format --check apps/api
apps/api/.venv/bin/python apps/api/scripts/export_openapi.py
npm --prefix apps/web run generate:api
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
npm --prefix apps/web run test:e2e
apps/api/.venv/bin/python scripts/scan_secrets.py --include-build
apps/api/.venv/bin/python apps/api/scripts/verify_environment_sources.py --lat 28.4595 --lng 77.0266 --gate --json
apps/api/.venv/bin/python apps/api/scripts/verify_corroboration.py --mode gemini --output /tmp/phase2b-gemini.json
apps/api/.venv/bin/python apps/api/scripts/verify_corroboration.py --mode full --output /tmp/phase2b-full.json
```

Use the documented Earth Engine Compose override for the read-only ADC mount when refreshing local containers. Do not add secrets to images, frontend variables, logs or verification artifacts.
