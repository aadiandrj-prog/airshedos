# Phase 1C verification — implementation ready, authenticated live gate pending

Recorded 11 September 2026. This report does **not** declare Phase 1C fully accepted or safe to merge: Earth Engine project/ADC setup is missing. The existing Google Maps and FIRMS keys cannot authenticate Earth Engine.

## Implementation and baseline

Started from the live-verified Phase 1B commit `32ca14fc9d72d1c78c52e7b166e1850522f60fd0`, on focused branch `codex/phase-1c-satellite`. Phase 1B PR #1 was still open at inspection; no merge was performed. The Phase 1C PR is based on `feat/phase-1b-environment` to keep its diff focused until Phase 1B merges.

Implemented only a Sentinel-5P availability/normalization boundary, additive API integration, generated frontend types, independent minimal satellite panel, one-hour cache, manual verification extension, tests and documentation. Original ground provider adapters, incident workflows, fixture scores/forecast and source-status enum remain intact. There is no Gemini, Vertex AI, new forecasting, source attribution, evidence fusion, imagery viewer or map overlay.

## Authentication and data contract

Official `earthengine-api` 1.7.43; backend Application Default Credentials resolved with `google.auth.default`, lazy `ee.Initialize` and explicit `EARTH_ENGINE_PROJECT` (fallback `GOOGLE_CLOUD_PROJECT`). No credentials are generated, stored in frontend code or committed. Missing project/ADC does not prevent startup. An optional read-only ADC Compose mount is supplied but cannot be live-tested until ADC exists.

| Product | Collection | Band | Native unit |
| --- | --- | --- | --- |
| NO₂ | `COPERNICUS/S5P/NRTI/L3_NO2` | `tropospheric_NO2_column_number_density` | `mol/m²` |
| CO | `COPERNICUS/S5P/NRTI/L3_CO` | `CO_column_number_density` | `mol/m²` |
| UV Aerosol Index | `COPERNICUS/S5P/NRTI/L3_AER_AI` | `absorbing_aerosol_index` | dimensionless |

QA: preserve catalog-ingested pixel masks (documented thresholds 0.75/0.50/0.80 respectively), require nominal product quality and processing metadata, mask column outliers below −0.001 mol/m², retain other negative columns and negative aerosol index. The L3 API has no original pixel QA band. The catalog's older >50 example commands differ from its stated ingestion thresholds; no per-pixel QA audit is claimed. See [exact rules and official sources](DATA_SOURCES.md#earth-engine--sentinel-5p).

Query: 10 km buffered point, center rounded to four decimals, default 72-hour window ending at the current UTC hour; explicit `at` uses the exact supplied end. Mean/count reduction at the catalog's 1,113.2 m grid; grid cells are not native footprints. Filter unusable scenes/reductions before choosing the newest by acquisition timestamp. Each product retains its own timestamp, scene/image ID, source product ID, QA, native footprint if supplied, retrieval time, age and provenance. No averaging across scenes or products.

## API, display, cache and performance

- `EnvironmentalContext.satellite` is additive and nullable. Existing three-source status keys are unchanged.
- `/api/v1/environment/satellite` shares the same implementation/cache as the full context endpoint; both accept optional `at` and `lookback_hours`.
- The browser requests ground context with `include_satellite=false` and loads satellite independently. A slow or failed satellite request does not delay or erase the original cards.
- A separate satellite section preserves the dark-green style, native values/units, age, quality, availability and expandable provenance. It explicitly states that atmospheric columns are not ground concentrations. The fictional incident is unaffected.
- Cache keys include rounded coordinate, exact time window, radius and fixed product set. TTL 3,600 seconds, using the existing bounded LRU/timer infrastructure. Genuine scientific absence is cached; operational failures are not. Cached observations retain acquisition/retrieval times and refresh age.
- One synchronous SDK batch runs in a thread, alongside asynchronous ground providers. Batch deadline 25 seconds; SDK/socket timeout 10 seconds; no compute retries. Completed products survive a timeout. An in-flight timed-out RPC keeps the provider reserved until it finishes, preventing repeated orphaned work. Default service lock-plus-lookup deadline 26 seconds. No background-worker infrastructure was introduced.

## Gurugram probe: actual result

Command, from `apps/api`:

```sh
python scripts/verify_environment_sources.py --lat 28.4595 --lng 77.0266 --gate --json
```

Actual request: **2026-09-11 16:07:35 UTC**. Default satellite window: **2026-09-08 16:00:00 UTC through 2026-09-11 16:00:00 UTC (exclusive)**. Radius 10 km. No coordinates, quality rules or time window were altered to obtain values. No wider debug window was used.

| Product | Status | Value | Unit | Observed / age | QA | RPC latency / cache |
| --- | --- | --- | --- | --- | --- | --- |
| NO₂ | `not_configured` | null | `mol/m²` | null / null | Not evaluated | No RPC / no cache hit |
| CO | `not_configured` | null | `mol/m²` | null / null | Not evaluated | No RPC / no cache hit |
| UV Aerosol Index | `not_configured` | null | dimensionless | null / null | Not evaluated | No RPC / no cache hit |

Local configuration check latency: **0.08 ms**; product latency fields are 0 because no RPC was attempted. **Authenticated Earth Engine latency and Gurugram coverage are unknown.** This is not `no_scene` or a verified empty observation. The script correctly exits **2** for the unmet satellite gate. Project identifiers, ADC configuration/file and Cloud CLI were absent at inspection; no service account or long-lived credential was created.

A final satellite-only rerun at **2026-09-11T16:27:42.605338Z** also returned `not_configured`, with **0 product queries** before/after the cache check and **0.12 ms** local handling. See [final satellite gate output](verification/phase1c-satellite-final.json). It exited 2; no remote Earth Engine request occurred.

The same full run reverified Phase 1B: AQ **LIVE, 2,706.97 ms**; Weather **LIVE, 1,997.75 ms**; NOAA-20 FIRMS **LIVE, 2,367.39 ms**. All three returned HTTP 200. Cache reuse preserved times/provenance and caused no additional HTTP responses (3 first / 3 final). Disabling Weather in the local verification service preserved cached AQ/FIRMS. Both Phase 1B gates passed. The original adapters were not modified.

Sanitized evidence: [Gurugram result](verification/phase1c-gurugram.json). Browser screenshots are **synthetic test evidence**, not live observations: [desktop](screenshots/phase-1c-synthetic-desktop.png), [mobile](screenshots/phase-1c-synthetic-mobile.png).

## Automated and operational checks

| Check | Result |
| --- | --- |
| Full backend tests | **113 passed in 6.26 seconds**, including all 76 Phase 1B cases |
| New offline SDK graph tests | PASS for all three products; real SDK serializes geometry, masks, reducers, time filters, descending usable selection and scene identity without network |
| Backend Ruff lint/format | PASS |
| Full Chromium browser suite | **13 passed in 7.0 seconds**, including all 8 Phase 1B tests |
| Frontend lint | PASS |
| Frontend type check | PASS |
| Frontend production build | PASS |
| OpenAPI/type generation | PASS; both generated files updated, export path now independent of calling directory |
| Docker build/start/health | PASS, both API and web healthy, non-root users, loopback ports |
| Secret scan | PASS; 0 findings in source, generated frontend build and live-verification output |
| Optional Docker ADC mount | Configuration provided; actual credential access not verified because ADC is absent |
| GitHub CI | Inspect the focused PR checks for the exact pushed revision; linked in the delivery response |

Automated fixtures are explicitly synthetic. Unit tests delete provider/project configuration and block HTTPX, Requests, httplib2 and Earth Engine compute transports unless individually mocked. SDK graph tests use the official package's bundled offline algorithm definitions. CI never runs the live verification script. Browser CI uses credential-free Docker services and synthetic response interception. Two pre-existing Starlette/HTTPX and AnyIO deprecation warnings remain.

## Deviations, limitations and next action

1. **Authenticated live acceptance is blocked**, not passed. The project owner must register/enable Earth Engine, supply the project ID, and configure backend ADC. Then run the fixed Gurugram satellite gate. Do not merge as fully verified before that succeeds or honestly returns genuine missing/filtered coverage.
2. The stable Phase 1B branch was used because PR #1 remained unmerged. No merge is performed automatically.
3. An independent satellite endpoint and `include_satellite=false` were added to prevent slow satellite work from blocking ground cards. The full context still includes satellite by default.
4. The default end is bucketed to the current UTC hour for deterministic cache reuse, excluding up to the latest 59m59s. Explicit `at` is exact. This is documented, not silently presented as continuous real-time coverage.
5. Pixel QA is inherited from L3, not fabricated or re-thresholded from a nonexistent band. Missing local pixels can combine QA exclusion and missing coverage. Non-nominal metadata is conservatively excluded; authenticated testing may reveal coverage limitations but filters must not be loosened merely to produce values.
6. Selected products can have different observation times within the window. No temporal alignment, interpolation, ground-concentration conversion or causal attribution is performed.
7. Cache and SDK coordination are process-local, matching the existing single-worker architecture. Long RPCs cannot be forcibly killed; subsequent queries report busy until cleanup.

Recommendation: finish **Phase 1C authentication and live verification first**, then review the focused PR. Do not begin Phase 2A or Gemini work from this delivery.
