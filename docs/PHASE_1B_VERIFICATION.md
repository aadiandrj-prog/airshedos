# Phase 1B delivery and verification

Verified locally on 11 September 2026. This delivery implements the environmental data foundation and the requested frontend refinement. **Credentialed live integration remains unverified because the user explicitly chose to proceed without keys.** No provider result was fabricated. Phase 1C and deployment were not started.

## Delivered

- `apps/api/app/environment/`: strict environmental models, provider protocols and Google AQ/Weather + NASA FIRMS implementations, bounded async HTTP, Haversine/bounding-box utilities, independent result aggregation, TTL cache, configuration and routes.
- `apps/api/app/main.py`: lifespan-owned HTTP client and injectable environmental service; incident repository and actions preserved.
- `apps/api/scripts/verify_environment_sources.py`: manual coordinate probe with concise or full normalized output, excluded from CI.
- `apps/api/tests/`: synthetic provider fixtures, network-blocking setup, normalization, failure, geo, cache, security and endpoint coverage.
- `apps/web/src/components/environment-panel.tsx`: independent coordinate probe, readings, units, source states, source timing, fire distances and clear attribution limits.
- `apps/web/src/app/`, `operations-pane.tsx`: charcoal-green visual refinement, editorial headings, responsive source cards, preserved command workflows.
- Generated `apps/api/openapi.json` and `apps/web/src/lib/api-schema.d.ts`, dependency locks, backend/frontend environment examples, Docker configuration, CI name, documentation and browser tests updated.

Models introduced: `EnvironmentalContext`, `EnvironmentalObservation`, `EnvironmentalProvenance`, `AirQualityObservation`, `AirQualityIndex`, `PollutantMeasurement`, `Measurement`, `MeteorologicalObservation`, `FireObservation`, `EnvironmentalSourceStatus`, `EnvironmentalSourceStatuses`, `EnvironmentalSources`, `ProviderConfiguration`, and `SourceState`.

Small async interfaces `AirQualityProvider`, `WeatherProvider`, and `FireProvider` are implemented by `GoogleAirQualityProvider`, `GoogleWeatherProvider`, and `NasaFirmsProvider`. No plugin framework was added.

New routes:

- `GET /api/v1/environment/context?lat=28.4595&lng=77.0266` with optional timezone-aware `at` reference metadata.
- `GET /api/v1/environment/sources` for configuration presence only.

The service returns partial context even if one/all providers fail. Google cache TTL is 600 seconds; FIRMS 900 seconds; exact coordinate keys; 256-entry process-local LRU; expiry timers; two HTTP attempts maximum; a deadline also bounds provider-lock waiting. No errors are cached, no secrets/raw bodies are logged, and no environment readings affect the fictional incident's scores or forecast.

## Automated checks

| Check | Result |
| --- | --- |
| Backend `ruff check .` | Pass |
| Backend `ruff format --check .` | Pass |
| Backend `pytest -q` | **72 passed**: all 24 Phase 1A tests plus 48 new cases |
| `python scripts/export_openapi.py` and frontend `npm run generate:api` | Regenerated; contract consistency verified |
| Compare all original routes and schemas to Phase 1A | No existing route or schema changed |
| Frontend `npm run lint` | Pass |
| Frontend `npm run typecheck` | Pass |
| Frontend `npm run build` | Pass, Next.js production output |
| `npm run test:e2e` against Docker app | **8 passed**, including all 3 Phase 1A scenarios |
| `docker compose -p airshedos-phase1a up --build -d --wait` | Both images built; API and web healthy |
| Secret-pattern scan of tracked/unignored source and docs | No findings; Google/GitHub/AWS/private-key patterns, credential-bearing FIRMS URLs and nonempty provider environment assignments checked |
| `.env`, `apps/web/.env.local`, `apps/api/.env` ignore checks | All ignored |
| `git diff --check` | Pass |

The backend retains two existing third-party deprecation warnings concerning Starlette/HTTPX and an AnyIO alias. No test failed. Browser tests initially exposed two overly broad test selectors; these were corrected before the passing run.

Tests explicitly block real HTTP transport and clear provider credentials. All successful provider payloads in automated tests are synthetic. Tests cover all-success, partial failure, missing Google credentials with FIRMS configured, all-unavailable, malformed payloads, 4xx/5xx, retries, timeout, coordinates/timezones, source units, empty detections, cache expiry/coalescing/capacity and secret-safe serialization/logging.

Browser checks exercise unconfigured providers against the real local backend; synthetic route interceptions exercise readings, cached states, partial availability, zero detections and errors. They also verify the browser makes no direct Google/NASA provider requests, and that incident acknowledgment/sharing, evidence expansion, retry/loading/empty states and reload persistence remain functional. Screenshots and additional layout inspection cover desktop/mobile and narrow-screen reflow. No horizontal overflow was found at 1280, 768, 640, 390 or 320 CSS pixels, and no uncaught browser errors occurred. The 640px check approximates 200% zoom reflow on a 1280px desktop; this is not a full accessibility audit.

## Actual NCR provider verification

Manual command from `apps/api`:

```sh
.venv/bin/python scripts/verify_environment_sources.py --lat 28.4595 --lng 77.0266
```

Actual request: **2026-09-11T03:03:45.796507+00:00** (08:33:45 IST), coordinate **28.4595, 77.0266**.

| Source | Actual state | Local processing latency | Normalized readings |
| --- | --- | --- | --- |
| Google Air Quality | NOT_CONFIGURED | 0.04 ms | null |
| Google Weather | NOT_CONFIGURED | 0.01 ms | null |
| NASA FIRMS | NOT_CONFIGURED | 0.00 ms | null; no claim of zero fires |

**Genuinely live sources: none.** No keys were supplied, no external provider request was made, and no observation/provenance was invented. The tiny latencies above measure local configuration handling, not network performance. Credentialed access, enabled APIs, geographic coverage and billing/quota remain to be checked using this same NCR probe when keys are supplied.

## Visual review

The design follows the supplied ZIP's dark atmospheric direction with pale green actions and serif headings. The live-context area and fictional incident area have distinct headings and clear labels. Existing workflows remain intact. No marketing hero, external images/fonts, map SDK or additional UI dependencies were introduced.

- [Desktop, actual unconfigured providers](screenshots/phase-1b-desktop.png)
- [Mobile, actual unconfigured providers](screenshots/phase-1b-mobile.png)
- [Desktop, synthetic renderer test](screenshots/phase-1b-mocked-readings.png)
- [Mobile, synthetic renderer test](screenshots/phase-1b-mocked-mobile.png)

**Screenshots with `mocked` in their names contain synthetic test values, not live observations.** The original Phase 1A screenshots and verification record remain preserved.

## Documentation and boundaries

README explains current setup, both environment-file locations, routes and manual checks. ARCHITECTURE describes provider isolation, models, cache, failure semantics and the creative direction. DATA_SOURCES links official Google/NASA references, configuration, normalization, attribution and limitations.

The direct user request to refine the frontend superseded the attached brief's “Do NOT redesign” restriction. This was a visual refinement; Phase 1A routes, schemas and actions were preserved. The optional `at` parameter is explicitly metadata-only because this phase permits current conditions. A single FIRMS stream (`VIIRS_SNPP_NRT`) is used; NASA announces S-NPP product delivery ends 1 November 2026, so a verified NOAA-20/21 transition is needed before then. See DATA_SOURCES for the primary reference.

Remaining limitations: no credentialed live verification; provider coverage/cadence/outages; process-local cache and incident state; spherical approximate distances; FIRMS thermal detections do not prove emissions or causation; Google AQ estimates are not a new regulatory station; no historical queries, live fusion scores, AI, maps, predictions, persistence, authentication or notifications.

Git delivery uses the focused branch `feat/phase-1b-environment` from the verified Phase 1A baseline, with commit message `feat: add live environmental data foundation`. Commit/PR links and hosted CI results are reported in the delivery response.

Recommended Phase 1C: after enabling and probing these providers, validate a narrowly scoped satellite atmospheric data adapter with explicit acquisition times, resolution, provenance and missing-data behavior. Do not turn that context into causal attribution. **No Phase 1C work was performed.**
