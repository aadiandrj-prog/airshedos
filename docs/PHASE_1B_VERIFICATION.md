# Phase 1B delivery and live verification

**Overall gate: PASS. Implementation verified and live providers verified.**

All three real providers authenticated and normalized successfully at the same fixed Gurugram coordinate. Cache reuse, a controlled partial failure, and real frontend display passed. This is a timestamped integration check, not a promise of continuous availability. No Phase 1C work or deployment was started; PR #1 has not been merged.

## Genuine live probe

Coordinate: **28.4595, 77.0266**, search radius **25 km**. Initial successful adapter probe: **2026-09-11T09:57:39.349323Z**. The repeatable cache/degraded-state gate below started at **2026-09-11T09:59:23.114308Z** (15:29:23 IST). Every value below belongs to that gate request, not a synthetic fixture.

| Provider | Configured | Live result | Fetch latency (ms) | Observation time (UTC) | Observation retrieved (UTC) | Second request |
| --- | --- | --- | --- | --- | --- | --- |
| Google Air Quality | YES | HTTP 200 / LIVE | 1773.21 | 2026-09-11T09:00:00Z | 2026-09-11T09:59:24.887471Z | CACHED / 0.38 ms |
| Google Weather | YES | HTTP 200 / LIVE | 1567.08 | 2026-09-11T09:59:24.539256Z | 2026-09-11T09:59:24.696652Z | CACHED / 0.34 ms |
| NASA FIRMS / NOAA-20 | YES | HTTP 200 / LIVE | 1612.7 | None: zero detections | 2026-09-11T09:59:24.744814Z | CACHED / 0.16 ms |

Successful authenticated HTTP 200 responses establish that Google Air Quality and Weather access was enabled and usable for this project/key at the probe time. No disabled-API, billing, key restriction, invalid-credential or quota error occurred. Credentials are present only in the ignored backend environment; no key or key fragment is recorded here.

### Representative normalized fields

Google AQ retained two independent scales:

- Universal AQI (`uaqi`): **30**, category **Low air quality**, dominant pollutant **pm10**.
- Indian NAQI (`ind_cpcb`, provider label `NAQI (IN)`): **175**, category **Moderate air quality**, dominant pollutant **pm25**.
- PM2.5 **38.63 µg/m³**, PM10 **139.95 µg/m³**, CO **1493.6 ppb**, NO2 **10.07 ppb**, O3 **27.69 ppb**, SO2 **5.33 ppb**, NH3 **65.45 ppb**.

Google Weather: **28.7 °C**, relative humidity **76%**, wind **10 km/h from 72° / EAST_NORTHEAST**, sea-level pressure **1007.25 mbar**, precipitation probability **44%**, QPF **0.55 mm**, cloud cover **94%**. Zero/nullable values and source units continue to be preserved. Wind is the origin direction, not a plume destination.

NASA FIRMS used the official global Area API with **VIIRS_NOAA20_NRT**, day range **2** (11 and 10 September UTC), bounding box **76.770865,28.234670,77.282335,28.684330** in west/south/east/north order. Its valid CSV normalized to **`fires: []`, status LIVE, count 0** within 25 km. The location was not changed to force a detection. With no returned detections, there is no observation time, satellite row, confidence, FRP or brightness value to invent. Positive-detection parsing, categorical confidence, UTC time parsing, distances and radius filtering remain covered by synthetic regression fixtures; no positive detection was live-verified at this probe.

AQ and Weather retain provider source IDs, lookup method, documentation URLs, explanatory notes and `is_demo: false`. FIRMS retains source identity, selected product, radius, window and retrieval time even for an empty response. No provenance is inferred for nonexistent observations. Modelled Google AQ is not a new regulatory station; thermal detections cannot establish pollution causation.

## Cache and controlled failure

Run from `apps/api` with the virtual environment active:

```sh
python scripts/verify_environment_sources.py --lat 28.4595 --lng 77.0266 --gate --json
```

The first context made **3 external requests**, one per provider, each HTTP 200. The second identical request at **2026-09-11T09:59:24.888548+00:00** returned **CACHED for all three**. The HTTP response counter stayed at **3**, with no new provider call. Observation values, original observation/retrieval times, and provenance matched; the selected FIRMS product was unchanged. Cache latencies are in the provider table above.

At **2026-09-11T09:59:24.890489+00:00**, Weather was disabled only through the local service's injected provider object. The context remained valid: **AQ CACHED + Weather NOT_CONFIGURED/null + FIRMS CACHED/[]**. Other results matched the prior context and the outbound response count stayed **3**. The original provider was restored; neither `.env` nor a real service was changed. No upstream failure was intentionally induced. The manual tool returns a nonzero exit status if its provider/cache/partial checks fail.

## Frontend and Docker

The existing Docker project was rebuilt and restarted with the root backend `.env`. Both API and frontend reported **healthy**, bound to loopback ports 8000 and 3000. No credentials were added to the frontend container or build arguments.

A separate real browser probe at **2026-09-11T10:02:46.101684Z** returned API HTTP 200 and **LIVE for all three**; Check conditions then returned **CACHED for all three**. Rendered values were compared with the actual backend response, units and source timing were visible, provenance was accessible, and the fictional incident retained its explicit DEMO label and separation. The browser made **zero direct Google/NASA requests**, had **zero uncaught errors**, and the 390px mobile layout had no horizontal overflow.

The browser probe crossed the hourly AQ update boundary after the manual gate: it displayed Universal AQI **48** and PM2.5 **36.37 µg/m³** at observation time **2026-09-11T10:00:00Z**. This is a later provider observation, not a substituted index or inconsistent normalization.

- [Live context, desktop with source timing expanded](screenshots/phase-1b-live-context.png)
- [Full command center, live desktop](screenshots/phase-1b-live-desktop.png)
- [Full command center, cached mobile refresh](screenshots/phase-1b-live-mobile.png)

These new captures contain real timestamped observations. Earlier `mocked` screenshots remain explicitly synthetic, and earlier unconfigured screenshots remain historical. Regression screenshots now go to ignored `apps/web/test-results` so automated tests do not overwrite curated evidence.

## Narrow implementation changes

No Google AQ or Weather response compatibility change was required: real payload structures matched the adapters. Additional returned pollutants such as NH3 were already handled without a fixed pollutant list. No raw live response fixture was needed.

FIRMS now accepts `FIRMS_DATASET`, defaults to **VIIRS_NOAA20_NRT**, and allows NOAA-21 or legacy S-NPP. This addresses NASA's announced S-NPP product retirement without adding multi-sensor fusion. The selected product is included in cache identity, normalized `fire_dataset`, observation IDs/provenance and the frontend label, including zero-detection results. OpenAPI and frontend types were regenerated together.

The developer-only verification script gained `--gate`, allowlisted HTTP status/count diagnostics, cache/provenance comparisons and a controlled local degraded-state check. Tests gained configurable-product and invalid-product coverage. The missing-credential browser scenarios now explicitly mock absence so they remain deterministic when local keys are present. Synthetic FIRMS fixture satellite identity matches the NOAA-20 default; no secrets or real raw provider responses were added to fixtures.

## Regression and security

| Check | Result |
| --- | --- |
| Backend `ruff check .` and `ruff format --check .` | PASS |
| Backend `pytest -q` | **76 passed**, including all 72 previous cases |
| OpenAPI export and `npm run generate:api` | PASS; generated schema/types updated together |
| Frontend `npm run lint` | PASS |
| Frontend `npm run typecheck` | PASS |
| Frontend `npm run build` | PASS |
| `npm run test:e2e` | **8 passed**; all existing incident workflows retained |
| Additional real-provider browser verification | PASS: LIVE → CACHED, values/units/provenance/demo separation |
| `docker compose -p airshedos-phase1a up --build -d --wait` | PASS, both services healthy |
| `git diff --check` | PASS |
| Secret-pattern scan before/after verification | PASS; actual credential values additionally checked against source, compiled frontend, normalized gate outputs and API logs |
| GitHub CI | Results for the pushed commit are linked in the delivery response / PR #1 |

Two existing third-party Starlette/HTTPX and AnyIO deprecation warnings remain. CI continues to use mocked provider responses and blocks real HTTP transport; no provider credentials were added to GitHub Actions. The root `.env` is ignored and excluded from Git. Docker build contexts exclude environment files, and the frontend container has no provider-key variables. Logs/verification artifacts were checked without printing secrets or credential-bearing URLs.

## Disposition and next phase

**No remaining Phase 1B gate blocker. Safe to merge within the local Phase 1B scope once the new commit's CI is green; merging remains a human decision.** Changes stay on `feat/phase-1b-environment`, PR #1, with commit message `fix: verify live environmental providers`. Exact commit and CI links are in the delivery response.

Limits remain: a single supported FIRMS product is queried at a time; zero detections cannot verify positive-row behavior against a live payload; provider coverage/cadence/outages and quotas can change; caches and incident actions remain process-local; no historical queries, causal attribution, maps, Gemini, satellite atmospheric evidence or Vertex AI predictions exist.

Recommended Phase 1C: define a narrow satellite atmospheric data-availability gate with explicit product resolution, acquisition times, quality masks, provenance and missing-data behavior. It must remain separate from the fictional incident. **Phase 1C was not started.**

## Initial implementation record

Commit `aaa32d4` initially passed 72 backend tests, 8 browser tests, builds, Docker, scans and CI while keys were absent. Its NCR probe at 2026-09-11T03:03:45.796507Z correctly returned NOT_CONFIGURED for all three. This historical implementation-only result is now superseded by the genuine live gate above; it was never presented as live integration evidence. Phase 1A's historical verification remains in [VERIFICATION.md](VERIFICATION.md).
