# Phase 2E verification — Google operational forecast

Date: 16 September 2026. Scope: official provider forecast only. Phase 2D remains **MODEL_NOT_ACCEPTED**; no custom model is deployed. Its selection code, negative result and locked November–December test artifacts were not modified or reopened. No Phase 3 work began.

## Implementation

A backend Google forecast adapter shares existing secure key handling, HTTP failure conventions and bounded cache infrastructure. The new `/api/v1/environment/forecast` endpoint serves 6/12/24-hour summaries from a canonical 24-hour batch. `CorroborationAssessment.forecast_outlook` is optional and attached after assessment; rules, source votes, support level and next-step advice do not consume forecast data. The existing current-context endpoint is unchanged. A shared frontend Forecast Outlook appears independently in the coordinate probe and after the citizen assessment. OpenAPI remains the source of frontend types.

[FORECASTING.md](FORECASTING.md) documents the precise API, native units, UTC times, thresholds, coverage/current-age requirements, provider attribution, 900-second cache and limitations. No new dependencies, database, trained prediction route, Vertex resource or model selection was introduced. The optional recorder/operational-priority concepts were intentionally omitted.

## Genuine Gurugram gate

Coordinates: **28.4595, 77.0266**. No alternate location/window was used to force success. Manual command: `apps/api/.venv/bin/python apps/api/scripts/verify_forecast.py` (never invoked by CI).

Requested: `2026-09-16T10:45:18.969738Z`. Retrieved: `2026-09-16T10:45:22.610091Z`. Current AQ valid at `2026-09-16T10:00:00Z`. Backend timestamps remain UTC; issuance time is **not supplied** and remains null.

Current Google PM2.5: **51.5 µg/m³**; current CPCB AQI: **88**, Satisfactory air quality. Both current and forecast returned live. All three horizons have complete pollutant/CPCB coverage.

| Horizon | PM2.5 peak µg/m³ | PM10 peak µg/m³ | Worst CPCB AQI | Provider category | PM2.5 peak UTC | Outlook |
| --- | --- | --- | --- | --- | --- | --- |
| 6h | 70.59 | 72.7 | 88 | Satisfactory air quality | 2026-09-16T16:00:00Z | WORSENING |
| 12h | 88.21 | 90.92 | 100 | Satisfactory air quality | 2026-09-16T22:00:00Z | SHARPLY_WORSENING |
| 24h | 91.46 | 93.74 | 168 | Moderate air quality | 2026-09-17T01:00:00Z | SHARPLY_WORSENING |

PM2.5 deltas versus current: +19.09 (+37.07%), +36.71 (+71.28%) and +39.96 (+77.59%) µg/m³. These are arithmetic peak comparisons, not probabilities. CPCB and PM peaks differ: 24h CPCB peak is 17 September 10:00 UTC; PM2.5 peaks at 01:00 UTC and PM10 at 00:00 UTC. Provider AQI values/categories are retained without recalculation from instantaneous PM.

Initial context latency: **3643.59 ms** (includes concurrent current AQ). Cached 6h response: **3.88 ms**. Exactly **one forecast HTTP request and one current-AQ request** were made; the second request added zero upstream calls. Original retrieval time and first six hourly points were identical. Cache and 6/12/24 coverage gates: **PASS**. No provider errors in this probe.

### Hourly trajectory captured from the provider

Native pollutant units are `MICROGRAMS_PER_CUBIC_METER`; index identity is `ind_cpcb`. Other pollutants retain their supplied units, including `PARTS_PER_BILLION`.

| Forecast valid time (UTC) | PM2.5 (µg/m³) | PM10 (µg/m³) | CPCB AQI |
| --- | --- | --- | --- |
| 2026-09-16T11:00:00Z | 49.38 | 50.14 | 88 |
| 2026-09-16T12:00:00Z | 49.48 | 50.53 | 88 |
| 2026-09-16T13:00:00Z | 53.45 | 54.81 | 88 |
| 2026-09-16T14:00:00Z | 61.56 | 63.33 | 88 |
| 2026-09-16T15:00:00Z | 67.66 | 69.59 | 88 |
| 2026-09-16T16:00:00Z | 70.59 | 72.7 | 88 |
| 2026-09-16T17:00:00Z | 74.1 | 76.32 | 91 |
| 2026-09-16T18:00:00Z | 81.9 | 84.59 | 92 |
| 2026-09-16T19:00:00Z | 82.74 | 85.41 | 93 |
| 2026-09-16T20:00:00Z | 84.19 | 86.76 | 94 |
| 2026-09-16T21:00:00Z | 86.69 | 89.4 | 97 |
| 2026-09-16T22:00:00Z | 88.21 | 90.92 | 100 |
| 2026-09-16T23:00:00Z | 90.53 | 93.23 | 104 |
| 2026-09-17T00:00:00Z | 91.3 | 93.74 | 108 |
| 2026-09-17T01:00:00Z | 91.46 | 93.62 | 116 |
| 2026-09-17T02:00:00Z | 82.96 | 84.93 | 123 |
| 2026-09-17T03:00:00Z | 60.87 | 63.63 | 124 |
| 2026-09-17T04:00:00Z | 49.4 | 54.52 | 124 |
| 2026-09-17T05:00:00Z | 41.58 | 46.48 | 122 |
| 2026-09-17T06:00:00Z | 37.19 | 40.41 | 119 |
| 2026-09-17T07:00:00Z | 37.44 | 40.53 | 117 |
| 2026-09-17T08:00:00Z | 38.07 | 41.18 | 116 |
| 2026-09-17T09:00:00Z | 37.43 | 40.65 | 143 |
| 2026-09-17T10:00:00Z | 36.36 | 39.46 | 168 |

Provenance: source `google_air_quality_forecast`, method “Google forecast:lookup; deterministic horizon summaries”, [official endpoint documentation](https://developers.google.com/maps/documentation/air-quality/forecast), actual retrieval timestamp above. Full normalized evidence (including current AQ, every index/pollutant and provenance) is in ignored local `data/verification/phase2e-gurugram.json`; credentials, request headers and raw upstream error bodies are excluded.

This demonstrates functioning integration only. It does not establish forecast accuracy or source causality. No historical forecast backtest was attempted. Google current and forecast AQ share one provider/model ecosystem.

## Existing live provider regression

The established `verify_environment_sources.py --lat 28.4595 --lng 77.0266 --gate --json` completed successfully after implementation. Google current AQ, Google Weather, NASA FIRMS NOAA-20 and Earth Engine returned live, with cache reuse and simulated independent weather-disabled response passing. Satellite scientific QA was not altered. Sanitized local artifact: `data/verification/phase2e-existing-providers.json`.

## Automated checks

- Full backend suite: **436 passed** in 30.23 seconds, including **48 new forecast tests**. Three non-failing existing dependency/platform warnings (Starlette/httpx, AnyIO alias and physical-core detection). Existing synthetic model round-trip tests run as regression checks; no historical model selection or locked-test evaluation was run.
- Browser suite: **31 passed** in 33.8 seconds (26 existing + 5 new forecast/integration cases). All browser forecast requests are intercepted, including when the local backend has credentials. Existing ground-reading assertion now targets its exact expected value to distinguish it from forecast explanatory text; no assertion was removed.
- Backend Ruff lint/format: **PASS**.
- Frontend lint, typecheck and production build: **PASS**.
- OpenAPI export and generated frontend types: **PASS**, byte-for-byte reproducible after regeneration.
- Docker API and web build/start/health: **PASS**, preserving the existing read-only ADC mount. No model-training dependencies added to the runtime image. A real HTTP check against the rebuilt Docker forecast endpoint returned 24 live hours, then cached 6h and 12h responses retaining the same retrieval timestamp (`2026-09-16T10:55:09.107916Z`).
- Secret scan: **PASS**, 1,767 source/build/artifact files scanned, zero findings. The root environment file and normalized live verification artifacts remain Git-ignored.
- Desktop and 390px mobile forecast screenshots visually inspected: source attribution, readable comparison fields, IST timestamps, separate outlook and no horizontal overflow. Screenshots are synthetic test output, not the live result above.
- Git whitespace validation: **PASS**. Phase 2D prediction/model code and result documents have no diff from baseline `6ef32b3`.
- GitHub push CI for implementation commit `e1d6eab`: **4/4 checks passed** (backend, browser, frontend, secrets), [run 35087399053](https://github.com/aadiandrj-prog/airshedos/actions/runs/35087399053). Final PR-head status is reported at completion.

Fixtures cover Google normalization, native units, CPCB identity/absence, all three horizons, earliest-tie peaks, threshold boundaries, zero/stale/future current readings, incompatible units, incomplete coverage, malformed payloads, pagination/cycle bounds, timeouts, authentication failures, source independence, concurrent request coalescing, cache expiry/copy isolation/horizon reuse, endpoint validation and provenance. The corroboration endpoint test changes forecast to an extreme value and then removes it, verifying every non-forecast assessment field remains identical.

## Limits and review

The 15-minute cache is process-local. New UTC hours create a new forecast window; errors and empty forecasts are not cached. Data availability, provider credentials/quota and network performance remain external dependencies. Missing CPCB never falls back silently to another scale. Partial PM2.5 coverage, stale current AQ or incompatible units withhold a trend classification. Provider issuance time and calibrated forecast accuracy are unknown.

The thresholds describe changes in the forecast peak versus current conditions, not regulation, temporal slope or incident risk. The advisory support result stays unchanged. No optional priority score or persistence was added. The rejected custom model is not exposed as a product feature and remains undeployed.

Next-phase recommendation: validate the officer review workflow and design a prospective provider-forecast evaluation protocol before alerts or automated action. This is a recommendation only; Phase 3A was not started.

Review: [draft PR #7](https://github.com/aadiandrj-prog/airshedos/pull/7), stacked on the existing Phase 2D branch. Implementation commit: `e1d6eab34cabb349a780b932d6bfa425410ccff0`. No PR was merged.
