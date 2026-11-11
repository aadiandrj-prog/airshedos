# Phase 1C verification — final metadata diagnostic passed

Updated 12 September 2026. **Diagnostic verdict B: a technically incorrect metadata predicate was corrected using authenticated Earth Engine scene properties and the official product manual.** Authenticated satellite query, cache and Phase 1B gates now pass. Scientific QA was not weakened to obtain values. Local regression results and final CI are recorded below; merging remains a human decision. The 11 September records are retained as historical evidence, not current blockers.

## Implementation and baseline

Started from the live-verified Phase 1B commit `32ca14fc9d72d1c78c52e7b166e1850522f60fd0`, on focused branch `codex/phase-1c-satellite`. Phase 1B PR #1 was still open at inspection; no merge was performed. The Phase 1C PR is based on `feat/phase-1b-environment` to keep its diff focused until Phase 1B merges.

Implemented only a Sentinel-5P availability/normalization boundary, additive API integration, generated frontend types, independent minimal satellite panel, one-hour cache, manual verification extension, tests and documentation. Original ground provider adapters, incident workflows, fixture scores/forecast and source-status enum remain intact. There is no Gemini, Vertex AI, new forecasting, source attribution, evidence fusion, imagery viewer or map overlay.

## Authentication and data contract

Official `earthengine-api` 1.7.43; backend Application Default Credentials resolved with `google.auth.default`, lazy `ee.Initialize` and explicit `EARTH_ENGINE_PROJECT` (fallback `GOOGLE_CLOUD_PROJECT`). No credentials are generated, stored in frontend code or committed. Missing project/ADC does not prevent startup. Host ADC is now configured and authenticated. The optional read-only ADC Compose mount remains available; Docker health/browser checks use the existing configuration without a credential mount. Authenticated Earth Engine gates run on the host.

| Product | Collection | Band | Native unit |
| --- | --- | --- | --- |
| NO₂ | `COPERNICUS/S5P/NRTI/L3_NO2` | `tropospheric_NO2_column_number_density` | `mol/m²` |
| CO | `COPERNICUS/S5P/NRTI/L3_CO` | `CO_column_number_density` | `mol/m²` |
| UV Aerosol Index | `COPERNICUS/S5P/NRTI/L3_AER_AI` | `absorbing_aerosol_index` | dimensionless |

QA: preserve catalog-ingested pixel masks (documented thresholds 0.75/0.50/0.80 respectively), require documented nominal product quality spellings and product-specific processing metadata, mask column outliers below −0.001 mol/m², retain other negative columns and negative aerosol index. The L3 API has no original pixel QA band. The catalog's older >50 example commands differ from its stated ingestion thresholds; no per-pixel QA audit is claimed. See [exact rules and official sources](DATA_SOURCES.md#earth-engine--sentinel-5p).

Query: 10 km buffered point, center rounded to four decimals, default 72-hour window ending at the current UTC hour; explicit `at` uses the exact supplied end. Mean/count reduction at the catalog's 1,113.2 m grid; grid cells are not native footprints. Filter unusable scenes/reductions before choosing the newest by acquisition timestamp. Each product retains its own timestamp, scene/image ID, source product ID, QA, native footprint if supplied, retrieval time, age and provenance. No averaging across scenes or products.

## API, display, cache and performance

- `EnvironmentalContext.satellite` is additive and nullable. Existing three-source status keys are unchanged.
- `/api/v1/environment/satellite` shares the same implementation/cache as the full context endpoint; both accept optional `at` and `lookback_hours`.
- The browser requests ground context with `include_satellite=false` and loads satellite independently. A slow or failed satellite request does not delay or erase the original cards.
- A separate satellite section preserves the dark-green style, native values/units, age, quality, availability and expandable provenance. It explicitly states that atmospheric columns are not ground concentrations. The fictional incident is unaffected.
- Cache keys include rounded coordinate, exact time window, radius and fixed product set. TTL 3,600 seconds, using the existing bounded LRU/timer infrastructure. Genuine scientific absence is cached; operational failures are not. Cached observations retain acquisition/retrieval times and refresh age.
- One synchronous SDK batch runs in a thread, alongside asynchronous ground providers. Batch deadline 25 seconds; SDK/socket timeout 10 seconds; no compute retries. Completed products survive a timeout. An in-flight timed-out RPC keeps the provider reserved until it finishes, preventing repeated orphaned work. Default service lock-plus-lookup deadline 26 seconds. No background-worker infrastructure was introduced.

## Historical Gurugram probe — 11 September 2026

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

## Original implementation checks — 11 September 2026

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

## Original limitations and disposition — 11 September 2026

1. **Historical blocker, resolved by the 12 September diagnostic below:** authenticated live acceptance was blocked. The project owner must register/enable Earth Engine, supply the project ID, and configure backend ADC. Then run the fixed Gurugram satellite gate. Do not merge as fully verified before that succeeds or honestly returns genuine missing/filtered coverage.
2. The stable Phase 1B branch was used because PR #1 remained unmerged. No merge is performed automatically.
3. An independent satellite endpoint and `include_satellite=false` were added to prevent slow satellite work from blocking ground cards. The full context still includes satellite by default.
4. The default end is bucketed to the current UTC hour for deterministic cache reuse, excluding up to the latest 59m59s. Explicit `at` is exact. This is documented, not silently presented as continuous real-time coverage.
5. Pixel QA is inherited from L3, not fabricated or re-thresholded from a nonexistent band. Missing local pixels can combine QA exclusion and missing coverage. Non-nominal metadata is conservatively excluded; authenticated testing may reveal coverage limitations but filters must not be loosened merely to produce values.
6. Selected products can have different observation times within the window. No temporal alignment, interpolation, ground-concentration conversion or causal attribution is performed.
7. Cache and SDK coordination are process-local, matching the existing single-worker architecture. Long RPCs cannot be forcibly killed; subsequent queries report busy until cleanup.

The original recommendation was to finish authentication and live verification before review. The final diagnostic below resolves that blocker. No Phase 2A or Gemini work is included.


## Final metadata diagnostic — 12 September 2026

**Verdict B — PASS.** The old predicate misclassified technically valid metadata; the inspected scenes were not marked degraded. This was not an intentional scientific exclusion. The provider design, selected bands, upstream pixel masks, QA thresholds, outlier cutoff, 10 km radius, 72-hour default window, reducer and cache policy are unchanged.

### Reproducible query and actual inspected properties

Authenticated metadata-only inspection at **2026-09-12 16:58:10 UTC**, Gurugram **28.4595, 77.0266**, radius **10 km**. Window: **2026-09-09 16:00:00 UTC → 2026-09-12 16:00:00 UTC, exclusive end**. This was the default current-hour 72-hour window at inspection. After the UTC hour advanced, the verification gate used `--at 2026-09-12T16:00:00Z` to hold the same candidate set for a direct before/after comparison; the window was neither widened nor shifted to force positive results.

The provider consults **`PRODUCT_QUALITY`** and **`PROCESSING_STATUS`**, with exactly that capitalization. All 11 scenes contain both properties; none is null. The original accepted value was the exact title-case string `Nominal` for both fields.

| Product | Candidates | Actual PRODUCT_QUALITY | Actual PROCESSING_STATUS | Exact old rejection |
| --- | --- | --- | --- | --- |
| NO₂ | 4 | `NOMINAL` | `NRTI-processing product` | Both equality predicates failed: quality casing and incorrect processing enum |
| CO | 4 | `NOMINAL` | `Nominal` | Product-quality casing only; processing predicate passed |
| UV Aerosol Index | 3 | `NOMINAL` | `Nominal` | Product-quality casing only; processing predicate passed |

Each inspected image is recorded below. Full IDs, timestamps, exact property values/presence, old expected values, individual rejection reasons and corrected predicate evaluations are in [the sanitized metadata artifact](verification/phase1c-metadata-diagnostic.json). “Pass after” means the scene-level predicate passes, not a claim about every pixel.

| Product / full image ID | Acquisition UTC | Old predicate | Corrected predicate |
| --- | --- | --- | --- |
| `COPERNICUS/S5P/NRTI/L3_NO2/20260912T075116_20260912T083033` | 2026-09-12T07:51:10Z | FAIL | PASS |
| `COPERNICUS/S5P/NRTI/L3_NO2/20260911T081116_20260911T084745` | 2026-09-11T08:11:10Z | FAIL | PASS |
| `COPERNICUS/S5P/NRTI/L3_NO2/20260910T083116_20260910T090632` | 2026-09-10T08:31:10Z | FAIL | PASS |
| `COPERNICUS/S5P/NRTI/L3_NO2/20260910T082616_20260910T090406` | 2026-09-10T08:26:10Z | FAIL | PASS |
| `COPERNICUS/S5P/NRTI/L3_CO/20260912T075116_20260912T081853` | 2026-09-12T07:51:10Z | FAIL | PASS |
| `COPERNICUS/S5P/NRTI/L3_CO/20260911T081116_20260911T083747` | 2026-09-11T08:11:10Z | FAIL | PASS |
| `COPERNICUS/S5P/NRTI/L3_CO/20260910T083116_20260910T085605` | 2026-09-10T08:31:10Z | FAIL | PASS |
| `COPERNICUS/S5P/NRTI/L3_CO/20260910T082616_20260910T085546` | 2026-09-10T08:26:10Z | FAIL | PASS |
| `COPERNICUS/S5P/NRTI/L3_AER_AI/20260912T075116_20260912T081855` | 2026-09-12T07:51:10Z | FAIL | PASS |
| `COPERNICUS/S5P/NRTI/L3_AER_AI/20260910T083116_20260910T085607` | 2026-09-10T08:31:10Z | FAIL | PASS |
| `COPERNICUS/S5P/NRTI/L3_AER_AI/20260910T082616_20260910T085549` | 2026-09-10T08:26:10Z | FAIL | PASS |

### Official semantics and narrow correction

The current Earth Engine catalogs list `PRODUCT_QUALITY` and `PROCESSING_STATUS` with generic title-case Nominal/Degraded descriptions: [NO₂](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_NO2), [CO](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_CO), [Aerosol Index](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_AER_AI). That metadata-value description does not fully match the actual official Earth Engine assets inspected here.

The [official Sentinel-5P NO₂ Product User Manual v4.5.0](https://sentiwiki.copernicus.eu/__attachments/1673595/S5P-KNMI-L2-0021-MA%20-%20Sentinel-5P%20Level%202%20Product%20User%20Manual%20Nitrogendioxide%202025-4.5.0.pdf?inst-v=48f4e5b4-21dc-4a3c-b262-15dde094f6bd), page 37, identifies `NRTI-processing product` as the near-real-time processing mode, separately from the OFFL nominal and backup modes. Page 143 defines product quality using uppercase `NOMINAL` and `DEGRADED`. Thus the NO₂ processing label is not a degraded-quality flag, and uppercase nominal is a genuine source enum rather than unknown quality.

The correction is narrowly bounded:

- Product quality accepts exact `Nominal` (catalog compatibility) and `NOMINAL` (actual source enum).
- NO₂ processing accepts exact `Nominal` (existing/catalog compatibility) or `NRTI-processing product` (documented NRTI mode).
- CO and Aerosol Index still require exact `Nominal` processing status; the NO₂ mode is not accepted for them.
- Missing, unknown, degraded and OFFL backup/nominal processing values remain rejected. No unrestricted case-folding, wildcard match, null acceptance or “anything except degraded” predicate was introduced.
- Server-side filtering and normalization use the same small allowlists. Domain/OpenAPI/generated TypeScript quality enums preserve the **raw accepted strings**, including `NOMINAL` and the NRTI label. No new UI or provider architecture was introduced.

The inherited L3 pixel masks already implement the catalog’s documented ingestion QA (NO₂ ≥0.75, CO ≥0.50, AER_AI ≥0.80). They remain intact. The column cutoff remains **−0.001 mol/m²**; valid negative columns and aerosol-index values remain allowed. Scene metadata is an additional selection criterion, and the old comparisons were stricter only because they compared against incompatible strings. **Scientific QA was not weakened merely to obtain data.**

### Authenticated verification after correction

```sh
python scripts/verify_environment_sources.py --lat 28.4595 --lng 77.0266 \
  --at 2026-09-12T16:00:00Z --lookback-hours 72 --gate --json
```

**Exit 0. Satellite provider LIVE; authenticated query PASS; cache PASS; Phase 1B PASS; overall satellite gate PASS.** The same 4/4/3 candidates now yield 4/4/3 accepted scenes. All three selected observations are usable. No wider historical/debug window was necessary or run.

| Product | Value (native unit) | Acquired UTC | Age at retrieval | Valid grid cells | Product query latency |
| --- | --- | --- | --- | --- | --- |
| no2 | 5.351062752739593e-05 mol/m² | 2026-09-12T07:51:10Z | 32992.35 s (~9.16 h) | 241 | 8664.09 ms |
| co | 0.04325115046353522 mol/m² | 2026-09-12T07:51:10Z | 32993.75 s (~9.16 h) | 320 | 1399.84 ms |
| aerosol_index | -1.2593098568040946 dimensionless | 2026-09-12T07:51:10Z | 32994.44 s (~9.17 h) | 323 | 690.94 ms |

Satellite total latency **10,759.15 ms**, subsequent cached response **0.68 ms**. The NO₂ timing includes lazy ADC/SDK initialization. Product-query calls remain **3 → 3**, with acquisition/retrieval times, values and provenance unchanged on cache reuse. Satellite units are not ground concentrations or AQI.

Phase 1B revalidation: Google AQ **LIVE (1,855.70 ms)**, Weather **LIVE (1,454.13 ms)**, NOAA-20 FIRMS **LIVE (1,633.40 ms)**; all HTTP 200. Cache and controlled Weather-disabled partial response passed, with **3 → 3** outbound HTTP responses. Full sanitized observations, scene IDs, QA, source timestamps and gate results: [authenticated diagnostic gate](verification/phase1c-authenticated-diagnostic-gate.json).

### Final regression and disposition

| Check | Result |
| --- | --- |
| Satellite tests | **66 passed in 0.69 s** |
| Full backend tests | **142 passed in 6.32 s** |
| Browser tests | **13 passed in 6.5 s** |
| Backend lint/format | PASS |
| Frontend lint/typecheck/production build | PASS |
| OpenAPI and generated TypeScript | Updated together; consistency verified before commit |
| Docker build/start/health | PASS; both existing services healthy |
| Secret scan | **PASS; 1,594 source/build/diagnostic files, 0 findings** |
| Authenticated same-window Gurugram gate | PASS, exit 0 |
| Phase 1B live/cache/partial failure | PASS |
| Wider debug window | Not needed; not run |
| GitHub CI | Exact pushed revision checks linked from PR #2 and the delivery response |

All existing tests are retained. Added regressions cover the actual uppercase/source mode strings, raw-metadata preservation, continued rejection of degraded/missing/unknown/OFFL modes, and the NO₂-only processing exception. Offline SDK graph tests verify the exact product-specific filtering expression; CI never makes live Earth Engine requests. The two existing dependency deprecation warnings remain.

**Phase 1C is safe to merge within its agreed local scope once the final checks above are green.** This diagnostic resolves the authenticated verification blocker. Review remains on the existing Phase 1C PR; no automatic merge and no Phase 2A work.
