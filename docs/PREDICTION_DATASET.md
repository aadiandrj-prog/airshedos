# Phase 2C historical prediction data contract

Status: **offline implementation and synthetic verification; real extraction pending**. The user explicitly chose fixtures while `OPENAQ_API_KEY` is absent. No real station selection, historical benchmark, full annual extraction or model readiness is claimed. Runtime incident, citizen evidence, environmental context and corroboration behavior remain unchanged.

## Availability is a separate gate

`prediction_dataset_v1` builds a **retrospective research frame**, not a proven operational backtest. A measurement timestamp and a publication timestamp are different. OpenAQ hourly interval endpoints do not establish when an observation or later revision was first available. ERA5-Land is retrospective reanalysis; hour-t weather is published after hour t. ECMWF describes delayed updates, including preliminary ERA5-Land-T availability around five days behind real time; Earth Engine ingestion may add delay. We therefore cannot honestly satisfy “known at or before t” with contemporaneous ERA5. See the [ECMWF product guide](https://confluence.ecmwf.int/spaces/CKB/pages/536218894/ERA5-Land%2Bhourly%2BAnalysis%2BReady%2BCloud%2BOptimised%2BARCO%2Bdata%2Bon%2Bsingle%2Blevels%2Bfrom%2B1950%2Bto%2Bpresent%2BProduct%2BUser%2BGuide%2BPUG).

The builder requires `--retrospective-research`. `available_at` remains unknown, `publication_availability_verified` is false and `ready_for_operational_training` is false. Observation-time checks can pass while `--require-operational` deliberately exits 2. No release timestamps or fixed “safe” delay are invented. Resolve the as-of data contract before Phase 2D: archive actual observation availability/revisions and use weather forecasts issued before t or demonstrably available lagged weather. No such new source is implemented here.

## Scope and selection

The study box is west/south/east/north **76.65, 28.25, 77.65, 28.90**, a core Delhi–NCR rectangle, not a legal NCR boundary. Only stationary OpenAQ monitoring locations with PM2.5 sensors qualify. Names are discovered, never hardcoded. Coordinates and timezone must be valid. Original location/provider/owner/license metadata and sensor IDs are preserved.

Default candidate window: **2025-01-01 00:00 UTC through 2026-01-01 00:00 UTC, end exclusive**, the latest complete calendar year at implementation. Discovery screens sensor metadata overlap, then measures actual hourly coverage for at most 12 candidate locations by default (configurable up to 50). More overlapping metadata duration is prioritized, with deterministic location-ID ties. This budget can bias geographic coverage; omitted candidates are explicitly listed. Metadata ranges alone do not prove coverage.

Each selected PM2.5 sensor needs at least **80% usable hours** across the common requested period, at least **three months with 80% coverage** for the full build, and usable six-hour targets. One highest-coverage sensor per location is chosen; ties use sensor ID. First station has highest measured coverage; subsequent stations maximize minimum geographic distance to selected stations among coverage-qualified candidates. The build rechecks measured coverage before weather extraction. Feasibility selection requires one well-covered month/partial-month instead of three. Expected sensors returning no observations receive explicit 100%-missing coverage rows.

Generate `candidate_coverage.csv` before accepting stations. It records every inspected station/sensor/pollutant/month and overall expected hours, valid hours, first/last usable times, missing percentage, longest missing gap, complete target windows and usable regression rows. `discovery_manifest.json` records available sensor ranges, request budget, evaluated locations and selection reasons. Full extraction requires 3–5 stations and at least 90 days; use approximately one year where coverage permits. If annual coverage fails, inspect monthly reports and rerun discovery for the **longest defensible common contiguous window** of at least 90 days, recording the reason in the verification report. The tool deliberately does not silently shorten dates or blend disparate station periods.

## Sources, units and quality

### Air quality

Use official [OpenAQ v3 `/sensors/{id}/hours`](https://docs.openaq.org/resources/measurements), the precomputed hourly mean resource. PM2.5 is the measured target, never Google Air Quality estimates. PM10, NO2, CO, O3 and SO2 are optional. Choose the coverage-selected PM2.5 sensor; optional sensors default to lowest ID and can be explicitly set using station `selected_sensor_ids`. Instruments are not blended, and an explicitly selected missing sensor fails.

Normalize compatible spellings of PM units to **µg/m³**, without changing values. Gases retain **ppb**, **ppm** or **µg/m³**, encoded in feature names to prevent unit mixing. Unexpected unit/product changes fail. Source interval `datetimeFrom` and `datetimeTo` must describe exactly one hour; the endpoint must be an exact timezone-aware UTC hour. No silent timestamp rounding. Non-hour-aligned source records currently fail rather than resample; check actual NCR source alignment at the live gate.

Use finite, nonnegative values only where `coverage.percentCoverage` is **75–100%**. This is a conservative dataset completeness rule, not a claim of instrument calibration or regulatory QA. Missing coverage metadata is unusable. All failed values remain missing with quality notes; raw values remain in cache. Exact duplicates collapse, retaining earliest retrieval; conflicting values, units, interval or coverage metadata fail rather than average revisions. There is no interpolation, forward-fill, gas conversion or outlier clipping.

The API key is loaded server-side by offline scripts from ignored `.env`, never sent to the browser. Create a key using the [OpenAQ setup guide](https://docs.openaq.org/using-the-api/quick-start), then add `OPENAQ_API_KEY=` locally. Never paste or commit it. Existing secret scans compare the configured key against Git-visible files and specified artifacts.

### Regional weather

Official Earth Engine Python API, existing backend Application Default Credentials and `EARTH_ENGINE_PROJECT` falling back to `GOOGLE_CLOUD_PROJECT`. No frontend SDK, new OAuth flow or service-account key. Collection: [ECMWF/ERA5_LAND/HOURLY](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY).

| Band | Native unit |
| --- | --- |
| temperature_2m | K |
| dewpoint_temperature_2m | K |
| surface_pressure | Pa |
| total_precipitation_hourly | m |
| u_component_of_wind_10m | m/s |
| v_component_of_wind_10m | m/s |

Sample the grid cell at each station coordinate with `Reducer.first` at **11,132 m** catalog scale. This is coarse regional context, not collocated weather-station measurement. Use Earth Engine's hourly precipitation band directly; do not difference it again. Negative precipitation packing artifacts become missing with a note; raw extraction remains cached. Wind speed is `hypot(u,v)`; meteorological wind-from direction is `degrees(atan2(-u,-v)) modulo 360`; calm direction is missing. No relative-humidity derivation is added.

Missing weather cells remain missing and appear in feature missingness. An entirely empty seven-day extraction chunk, malformed result or out-of-query station/hour fails, preserving cached progress. A feasibility artifact cannot authorize a larger build unless each station has at least 80% core temperature/pressure/wind coverage and 24 usable target rows.

### Optional sources deferred

Historical fires are excluded from this first frame. The suggested [NASA/LANCE/NOAA20_VIIRS/C2](https://developers.google.com/earth-engine/datasets/catalog/NASA_LANCE_NOAA20_VIIRS_C2) is a daily raster; its documented bands do not supply exact within-day detection acquisition times. Treating every daily pixel as available at midnight would leak future events. An isolated, tested exact-event helper counts 25/50/100 km detections in `(t−24h,t]`, requiring both observation and known availability at or before t. It has no live extractor and is not in the feature allowlist. Missing extraction is not encoded as zero fire pressure. Fire detections would not establish causality.

Sentinel-5P is deferred as an optional later ablation because of sparse asynchronous observations and publication-time alignment. No future satellite backfill, mandatory satellite completeness, satellite columns or changes to the Phase 1C provider are introduced.

## Frame and target definitions

Canonical key: **station ID + hourly UTC interval end t**. Preserve station timezone; calendar features use station-local hour, day of week (Monday=0), month and weekend. Calendar hour is integer local hour; Indian UTC half-hour offset is retained through timezone conversion.

Per station, reindex onto a complete hourly grid including **30 warmup days** before the requested output period. Never shift across station boundaries or across missing hours as though they were adjacent measurements.

Features:

- `pm25_t`, `pm25_lag_{1,2,3,6,12,24}h` in µg/m³.
- `pm25_rolling_mean_{3,6,12,24}h` and `pm25_rolling_std_{6,24}h` in µg/m³. Require every hour in `[t−(N−1)h,t]`; population standard deviation uses `ddof=0`.
- `history_count_30d` and `trailing_30d_p{85,90,95}_pm25`, using `(t−30d,t]`. Require **576 of 720 hours (80%)** and the full warmup duration. No percentile from a handful of observations.
- `hour_of_day`, `day_of_week`, `month`, `weekend` in station timezone.
- Optional pollutant current and one-hour lag, with native unit in the name, e.g. `no2_ppb_t`, `no2_ppb_lag_1h`. Missing optional pollutants do not delete rows.
- Six `era5_` source bands plus `era5_wind_speed_mps`, `era5_wind_from_degrees`. These remain retrospective and block operational eligibility.

Targets are strictly separate from the feature allowlist:

- **future_max_pm25_6h**: same-station maximum of t+1 through t+6, µg/m³.
- **future_mean_pm25_6h**: same-station mean of those six hours, µg/m³.
- Require **all six future observations**. `regression_eligible` also requires current PM2.5. Missing targets stay missing; do not infer a six-hour maximum from partial coverage.
- **spike_next_6h**: future max >= trailing percentile AND >= current × (1+relative increase) AND strictly greater than current. The last guard prevents stationary zero values becoming “spikes.” Valid current/future/history are required. This is an operational heuristic, not CPCB regulation, epidemiology or a validated health threshold.

Evaluate exactly p85/p90/p95 × 20%/25%/30% increases using **training rows only**. Predeclared selection: >=100 labeled training rows, prevalence 5–35%, closest to 20%; ties prefer p90 then 25%. Freeze before validation/test evaluation. If none qualify, report insufficient labels/extreme imbalance and leave the secondary target unavailable; never tune on test prevalence to force balance. The primary regression targets remain available. Real-data rule and prevalence are pending.

## Splits, leakage checks and evaluation

Aligned chronological approximately 70/15/15 for all stations; no shuffle. For periods >=180 days choose the nearest calendar-month boundaries; otherwise use exact hours. Purge the last six origin hours in each split so the **last target timestamp precedes the next split boundary**. Final six hours of the overall window cannot have complete targets and are purged too. Adjacent six-hour outcomes overlap within a split; no claim of independent observations or confidence intervals is made.

For a complete 2025 frame, boundaries are train `[2025-01-01,2025-09-01)`, validation `[2025-09-01,2025-11-01)`, test `[2025-11-01,2026-01-01)`, before purging. Labels may use known historical context from the preceding split; a later test row may use earlier measured test hours under rolling issuance. No scalar, imputer, station normalization or fitted model is trained in this phase. Any later learned preprocessing must fit on training only.

The validator checks file and contract checksums, rebuilds the frame from normalized source snapshots, compares the exact feature allowlist and training-only rule, and checks reconstructed features/targets/splits and lineage timestamps. Independent numerical tests and future-data perturbations test the construction logic itself. File checksums detect accidental modification; they do not prove provider authenticity or historical release times. `feature_matrix` defaults to rejecting unverified operational availability. Explicit retrospective export is possible, with target columns still excluded.

Baseline regression predicts future max with current PM2.5 (persistence) or full recent six-hour mean. Report MAE/RMSE in µg/m³ on the **same eligible rows** for fair comparison, plus total eligible counts and per-station metrics. Classification compares always-negative and current PM >= frozen trailing percentile. Report precision/recall/F1, prevalence, confusion counts and undefined-denominator flags; zero denominator scores are 0, empty populations are null. Synthetic scores validate calculations only; they say nothing about NCR predictability.

For >=3 stations prepare a station-holdout plan: fixed highest lexicographically sorted station ID, excluded from training and all fitting, evaluated separately on its chronological validation/test periods. This plan does not change the primary all-station split or train a model.

## Bounded extraction and reproducibility

OpenAQ uses 28-day chunks, pages of 1,000, at most 100 pages per query and 1,800 uncached HTTP attempts per process. Requests are at least two seconds apart (30/minute), below the documented [60/minute, 2,000/hour limits](https://docs.openaq.org/using-the-api/rate-limits). Run one extractor at a time; budgets are process-local, not coordinated across processes. Retry at most three attempts, honoring `Retry-After`; a requested pause >60 seconds stops for a resumable later run. HTTP timeouts are 45 seconds. Repeated pages or reaching a page cap fail instead of truncating silently. Metadata `found` values such as `>1000` are not treated as exact totals.

Earth Engine batches **all selected stations per seven-day chunk**, at most 168 hourly images per RPC, 60-second deadline and no automatic client retries. Restart resumes from successful cache entries. A 12-month build plus 30 warmup days requires approximately 57 such weather RPCs, not one per row. Actual RPCs/runtime remain pending. Logs summarize source, station, chunk, rows, cache and elapsed time; no credentials or full responses.

`data/` is Git-ignored. Cache entries use source + version + canonical query (IDs, coordinates, bands, range) hash, store original response, retrieval timestamp and SHA-256, and are atomically written. Frozen historical snapshots have **no TTL**; changing source/query creates a separate entry. Rerunning an identical build reuses cache. Intentionally refresh into a new cache directory to preserve prior revisions. Overlapping but differently bounded queries may need new requests. A failure never silently substitutes data.

Generated artifacts:

- `normalized_aq.parquet`, `normalized_era5.parquet`, `prediction_frame.parquet`.
- `dataset_manifest.json`: version, Git commit/dirty flag, build time, source/station/sensor identities, coordinates, feature/target definitions, native units, row counts, missingness, exact splits, artifact/contract hashes, timing and limitations.
- `source_manifest.json`: source queries, retrieval times and cache checksums; no key/header storage.
- `station_coverage.csv`, `split_manifest.json` including holdout plan, `target_analysis.json`, `baseline_metrics.json`, `leakage_report.json`.
- Discovery separately emits `candidate_coverage.csv`, `discovery_manifest.json`, `selected_stations.json`. Failures write sanitized `last_failure.json`; successful reruns should be judged by current manifests/exit status, not an older failure file.

Offline dependencies live in `requirements-dataset.lock`; they are not installed into API Docker images or imported by FastAPI. CI installs them for deterministic tests and forbids live networking.

## Commands

Run from the repository root:

```sh
uv pip install --python apps/api/.venv/bin/python -r apps/api/requirements-dataset.lock
apps/api/.venv/bin/python apps/api/scripts/build_prediction_fixture.py
apps/api/.venv/bin/python apps/api/scripts/validate_prediction_dataset.py --output data/processed/fixture_v1
apps/api/.venv/bin/python apps/api/scripts/evaluate_prediction_baselines.py --output data/processed/fixture_v1
# Expected failure: a retrospective fixture is not operationally available at t.
apps/api/.venv/bin/python apps/api/scripts/validate_prediction_dataset.py --output data/processed/fixture_v1 --require-operational
```

The fixture command marks all artifacts synthetic, generates three explicitly synthetic locations and makes **zero remote calls**. It cannot satisfy the real feasibility gate.

After OpenAQ configuration, execute a real 28-day gate first. The following dates are an explicit reproducible example within the intended annual window, not a claim of coverage:

```sh
apps/api/.venv/bin/python apps/api/scripts/discover_prediction_stations.py --start 2025-10-01T00:00:00Z --end 2025-10-29T00:00:00Z --feasibility --count 2 --output data/processed/discovery_gate
apps/api/.venv/bin/python apps/api/scripts/build_prediction_dataset.py --start 2025-10-01T00:00:00Z --end 2025-10-29T00:00:00Z --feasibility --stations data/processed/discovery_gate/selected_stations.json --retrospective-research --output data/processed/real_gate
apps/api/.venv/bin/python apps/api/scripts/validate_prediction_dataset.py --output data/processed/real_gate
```

Then inspect the candidate coverage report and record final station reasons before full extraction:

```sh
apps/api/.venv/bin/python apps/api/scripts/discover_prediction_stations.py --count 5 --output data/processed/discovery_full
apps/api/.venv/bin/python apps/api/scripts/build_prediction_dataset.py --stations data/processed/discovery_full/selected_stations.json --gate-directory data/processed/real_gate --retrospective-research --output data/processed/prediction_v1
apps/api/.venv/bin/python apps/api/scripts/validate_prediction_dataset.py --output data/processed/prediction_v1
apps/api/.venv/bin/python apps/api/scripts/evaluate_prediction_baselines.py --output data/processed/prediction_v1
```

If using a fallback range, pass identical explicit `--start`/`--end` to discovery and build, preserve the annual discovery report, and document the common-period evidence. Review source licensing before redistribution; datasets remain local and ignored. Never commit raw responses, `.env`, ADC files or tokens.

## Phase 2D decision

Do not begin training yet. First complete real multi-week extraction, coverage-based annual/common-period selection, final artifacts/benchmarks and the operational availability design. NCR monitors do not represent every street; ERA5 is regional reanalysis; optional fire and satellite observations cannot establish pollution sources. This is not a health-risk or regulatory model. Any future forecast requires prospective validation. No Vertex training job, prediction endpoint, forecast UI or corroboration change is included.
