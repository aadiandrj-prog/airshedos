# Phase 2C historical prediction data contract

Phase 2C provides an offline, reproducible data pipeline. Real acceptance results and acceptance checks are recorded in [PHASE_2C_VERIFICATION.md](PHASE_2C_VERIFICATION.md). No model is trained, no Vertex job is submitted, and no runtime environmental, citizen-evidence, corroboration or forecast UI behavior is changed.

## Two explicit feature profiles

`prediction_dataset_v2` defaults to **OPERATIONAL_V1**. It contains buffered AQ history and deterministic calendar features. **RESEARCH_ENRICHED_V1** adds unbuffered retrospective AQ and ERA5 and is labeled **NOT DEPLOYMENT-SAFE AS CURRENTLY SOURCED**. The profiles share source snapshots and caches.

Observation time is not publication time. OpenAQ historical hourly intervals do not establish when the value or a revision first became available. `AQ_AVAILABILITY_BUFFER_HOURS` defaults to **72**, configurable from 1 to 168 hours through the backend environment or CLI. At forecast origin t, AQ inputs must end at or before **t−buffer**. The initial prospective snapshot on 2026-09-14 found the two gate feeds approximately **69.25 hours stale**. One- or two-hour buffers were therefore not defensible from that snapshot. Seventy-two hours is a provisional assumption based on feed freshness, not a measured historical publication-delay guarantee or an accuracy optimization.

Known revised observations and known releases later than their assumed buffered deadline are conservatively excluded from operational inputs. Unidentified historical revisions remain a risk. Every output records `publication_availability_verified=false`; retrospective retrieval time is never substituted for historical availability. A machine `deployment_safe=true` for a buffered AQ feature is explicitly **conditional**, not proof. The exporter requires the matching availability manifest and explicit `accept_conditional_availability=True`; without that acknowledgment it fails. Research features cannot pass operational export even with acknowledgment. Prospective validation and revision handling remain prerequisites for serving predictions.

ERA5-Land is retrospective reanalysis with delayed publication. The [ECMWF guide](https://confluence.ecmwf.int/spaces/CKB/pages/536218894/ERA5-Land%2Bhourly%2BAnalysis%2BReady%2BCloud%2BOptimised%2BARCO%2Bdata%2Bon%2Bsingle%2Blevels%2Bfrom%2B1950%2Bto%2Bpresent%2BProduct%2BUser%2BGuide%2BPUG) describes preliminary updates around five days behind real time; Earth Engine ingestion may add delay. No ERA5 band or derivative enters OPERATIONAL_V1. Future weather, fires, satellites and AQ are also excluded.

## OpenAQ and objective station selection

Use official [OpenAQ v3 hourly resources](https://docs.openaq.org/resources/measurements) and [sensor metadata](https://docs.openaq.org/resources/sensors). The geographic study box is longitude **76.65–77.65**, latitude **28.25–28.90**, India, stationary monitors only. It is a core NCR study area, not an administrative boundary or exhaustive government-monitor inventory. Discovery starts with IDs and measured coverage, not preferred station names.

Inventory includes location/sensor IDs, coordinates, provider, instruments, timezone and first/last timestamps. Metadata `coverage.observedCount` counts underlying measurements and is **not** an hourly count. Actual hourly counts, monthly missingness and longest gaps come from `/hours` responses. Expired replacement sensors are listed but not blended with current sensors. Select the strongest sensor at a location by actual PM2.5 coverage. Require **80% usable hours**, at least three adequately covered months for full builds, and valid complete future windows. Geographic spread is considered only after this quality gate. Select 2–5 qualifying locations. The full audit inventories all PM2.5 sensors and measures those with at least 90 days of metadata overlap; unqueried expired sensors are labeled explicitly.

Prefer 2025-01-01 through 2026-01-01 UTC. If it is unsupported, select a documented common period of at least 90 days, preferably six months or longer, using measured coverage. No different per-station output periods are silently mixed. A genuine two-station, 14–31-day AQ plus ERA5 feasibility artifact must pass before the full hourly audit/build. Synthetic artifacts cannot unlock it. Each gate station needs at least 24 complete operational PM feature/target rows and at least 80% hours with all six usable ERA5 bands.

### Timestamp, units and QA contract

Preserve source `datetimeFrom` and `datetimeTo`, requiring exactly one hour. Real CPCB hourly endpoints occur at **:30 UTC**, corresponding to whole local hours in Asia/Kolkata. The canonical grid retains this phase; supported phases are :00 and :30, consistent within a sensor/station. Never floor, round, interpolate or silently resample AQ records. Query-window boundaries remain whole UTC hours. Station calendar features use the recorded timezone.

PM2.5/PM10 retain **µg/m³** (equivalent source Unicode spellings canonicalized). Optional gases retain their actual µg/m³, ppb or ppm units in column names; no conversion is performed. Reject unexpected product/unit changes. Use only finite, nonnegative values with **75–100% hourly coverage** and no explicit `flagInfo.hasFlags=true`. Missing coverage metadata remains unusable. This completeness rule is not instrument-certification or regulatory QA. Raw rejected values stay cached; normalized values stay missing. Exact duplicates collapse; conflicting values, units, intervals or coverage fail rather than average revisions.

The real feasibility data has recurrent 50%-coverage hours around 01:00 local time. These remain missing. They prevent complete 24-hour rolling windows, so the two 24-hour rolling features are excluded from OPERATIONAL_V1 and recorded as excluded candidates in its availability manifest. They remain visible as missing in research. No QA threshold is reduced and no gap is filled to create a feature.

## ERA5 live extraction

Use the official Earth Engine Python API, existing backend ADC and `EARTH_ENGINE_PROJECT` falling back to `GOOGLE_CLOUD_PROJECT`. No new credentials, frontend OAuth or service-account key. Collection: [ECMWF/ERA5_LAND/HOURLY](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY).

| Band | Native unit |
| --- | --- |
| temperature_2m | K |
| dewpoint_temperature_2m | K |
| surface_pressure | Pa |
| total_precipitation_hourly | m |
| u_component_of_wind_10m | m/s |
| v_component_of_wind_10m | m/s |

A server-side station map applies [`Image.reduceRegion`](https://developers.google.com/earth-engine/apidocs/ee-image-reduceregion) with `Reducer.first` at **11,132 m**. All stations and up to 168 hours remain batched in **one RPC per seven days**, not one RPC per row. Live diagnostics showed the earlier `reduceRegions` expression returned nulls at these point features while `reduceRegion` at the identical point/image returned six native values. The extraction-version field in the cache query distinguishes corrected results and preserves old diagnostic responses.

Research rows at 12:30 UTC join the latest ERA5 analysis at 12:00, never 13:00. This backward alignment does not resolve publication delay and does not make weather deployment-safe. Use the source hourly precipitation band directly without a second deaccumulation; negative packing artifacts become missing with a note. Wind speed = `hypot(u,v)`; wind-from direction = `degrees(atan2(-u,-v)) mod 360`; calm direction is missing. No relative humidity is inferred. Empty chunks, all-null band results, duplicate station-hours, malformed or out-of-query rows fail and preserve cached progress.

ERA5 is regional reanalysis, not a collocated weather instrument. Fire and Sentinel-5P features remain deferred. The proposed NOAA-20 daily raster lacks exact within-day acquisition times for safe hourly windows. The isolated exact-event helper remains tested but unused. No fire pressure is fabricated from missing extraction, and no causal source attribution is made.

## Features and targets

Canonical key: station ID + native UTC hourly interval end **t**. Reindex separately per station onto a complete grid. Operational extraction includes **30 days plus the AQ buffer** before the requested period (33 days at the default). Warmup rows are excluded from final output.

OPERATIONAL_V1 at the default 72-hour buffer includes:

- `pm25_latest_available` = measured value exactly t−72h, without forward-fill.
- PM2.5 lags **73, 74, 75, 78, 84, 96 hours**. For another buffer, admitted existing lags must exceed the buffer, plus buffer+1/2/3/6/12/24.
- Complete trailing means **3/6/12 hours** and population standard deviation **6 hours**, ending at t−buffer.
- Thirty-day history count and p85/p90/p95; require at least **576 of 720 hours** and the full history duration for percentiles.
- Station-local hour, weekday, month and weekend.
- Available optional PM10/NO2/CO/O3/SO2 lags at buffer and buffer+1, preserving their native unit. Missing optional inputs are not imputed and do not invalidate the PM-only core population.

RESEARCH_ENRICHED_V1 contains PM2.5 at t, lags 1/2/3/6/12/24, complete rolling means 3/6/12/24, std 6/24, unbuffered trailing history, calendar, optional current/lag1 pollutant values, six ERA5 bands and two wind derivatives. It is separately labeled and exported.

The input buffer **does not shift targets backward**. At the 72-hour default, t+1…t+6 is 73–78 hours after the latest input measurement. Primary **future_max_pm25_6h** and secondary continuous **future_mean_pm25_6h** use exactly the same station's **t+1…t+6** values in µg/m³, requiring all six. `regression_eligible` requires those targets and the profile's primary PM input. `operational_eligible` additionally requires all PM core lag/rolling features and excludes purged rows. Optional covariates and missing 30-day percentiles are reported separately; a later model must explicitly select usable features. `feature_complete` reports completeness of every admitted feature, including optional ones.

The secondary spike label requires future max ≥ trailing percentile, ≥ latest profile-eligible PM × (1+relative increase), and strictly greater than that PM. It requires the full trailing-history rule. Evaluate only the predefined **p85/90/95 × 20/25/30%** grid on **training data only**, using operational-eligible rows for the operational profile. Require ≥100 labels and 5–35% prevalence, choose closest to 20%, ties preferring p90 then 25%. If no rule qualifies, leave the secondary formulation unavailable; do not tune validation/test to force balance. It is an unvalidated heuristic, not a regulatory or health definition. Regression remains primary.

## Splits, validation and baselines

Use aligned chronological approximately 70/15/15 splits. For ≥180 days, choose nearest month boundaries; otherwise exact-hour boundaries. Purge six origin hours at each boundary so the last target precedes the next split. No random split, learned scaler, imputer or model fitting. Earlier historical context may be used by later split rows under rolling issuance; adjacent outcomes within a split overlap and are not statistically independent.

Validators check artifact/contract hashes, reconstruct the frame from normalized snapshots, compare feature lists and frozen train-only rules, and verify exact lags, rolling windows, future targets, station isolation, timestamp cutoffs and split purging. The machine availability manifest must exactly match the profile/feature columns. Operational validation rejects ERA5, unsafe/unknown features, target leakage and cutoff violations. Passing means **the conditional buffered contract is enforced**, not that historical publication/revision freedom is proven. Independent numerical and future-perturbation tests verify the reconstruction logic.

Persistence predicts the future six-hour maximum using the latest profile-eligible PM value. Recent mean uses six complete past hours ending at the same availability cutoff. Both report MAE/RMSE in µg/m³ on the same population, including per-station metrics. Operational baselines use complete operational PM feature rows. Classification reports always-negative and latest-PM ≥ frozen trailing-percentile baselines, precision/recall/F1, prevalence, confusion counts and zero-denominator flags. Empty populations remain null. These are real retrospective benchmarks only, not a prospective skill claim.

For ≥3 qualifying stations, the split manifest prepares a separate fixed-station holdout plan. The highest lexicographically sorted station ID is excluded from future fitting; its chronological validation/test periods are reserved. Any data-dependent spike rule must be refrozen using only the remaining training stations, rather than reusing the primary pooled rule. This does not replace the primary split or train a model.

## Caching, rate limits and artifacts

OpenAQ uses 28-day chunks, 1,000-row pages, maximum 100 pages per query, and 1,800 uncached attempts per process. Requests are at least two seconds apart, below the documented [60/minute and 2,000/hour limits](https://docs.openaq.org/using-the-api/rate-limits). Only allowlisted response quota/date headers are recorded. Stop if remaining quota falls to five or below. Do not run simultaneous OpenAQ extractors. Three bounded attempts honor Retry-After; a >60-second requested pause stops for a resumable later run. Repeated pages, pagination caps and unexpected responses fail rather than truncate.

Earth Engine uses a 60-second deadline with no automatic retries. Identical windows reuse frozen cache entries with no TTL. Raw cache identity remains `prediction_dataset_v1` to preserve compatible source snapshots across frame-version changes; corrected ERA5 queries include their extraction method. All entries record source, query, retrieval time and SHA-256 and are written atomically. Different query boundaries can require new requests. Raw AQ/weather are shared between profiles; generated profile Parquets are separate for self-contained validation.

Each CLI run persists unique timestamped `runs/*.json` counters, status and sanitized quota metadata, including failures. Earlier interrupted runs without these counters must not have request totals inferred from successful cache writes.

Generated artifacts remain under ignored `data/`:

- `prediction_frame.parquet`, `normalized_aq.parquet`, `normalized_era5.parquet` in the operational output, with research equivalents under `research_enriched_v1/`.
- `feature_availability_manifest.json`: every included feature and excluded candidate, source, historical/assumed availability, buffer, deployment-safe boolean, conditional flag, reason and revision risk.
- `dataset_manifest.json`: code/version, source IDs, native units, feature/target definitions, counts, missingness, exact boundaries, timings and checksums.
- `source_manifest.json`, `station_coverage.csv`, `row_attrition.json`, `split_manifest.json`, `target_analysis.json`, `baseline_metrics.json`, `leakage_report.json`.
- Full discovery audit: `candidate_inventory.json`, per-sensor normalized snapshots, monthly `candidate_coverage.csv`, selection and request statistics. Metadata-only candidates are explicitly distinguished from measured ones.

Attrition categories overlap and are not added as if mutually exclusive. Buffer losses and recoveries compare target+primary-input eligibility at zero versus configured buffer, holding targets fixed. Feature completeness and purging are separate counts.

## Prospective diagnostic and commands

`probe_openaq_availability.py` performs one fresh, bounded poll for selected sensors. It saves first-seen time/value, hourly interval, lag upper bound, prior-poll lower bound only where supported, and later revisions. First sightings on the initial poll are left-censored: old records could have been available much earlier. A fresh poll cache prevents historical cache hits being misrepresented as current availability. No recurring job or days-long study is started automatically.

```sh
# Install offline-only dependencies; never imported by FastAPI or API Docker images.
uv pip install --python apps/api/.venv/bin/python -r apps/api/requirements-dataset.lock
# Synthetic smoke evidence only; never unlocks the live feasibility gate.
apps/api/.venv/bin/python apps/api/scripts/build_prediction_fixture.py
# Inspect real candidates and choose two for the bounded gate.
apps/api/.venv/bin/python apps/api/scripts/discover_prediction_stations.py --start 2025-10-01T00:00:00Z --end 2025-10-29T00:00:00Z --feasibility --count 2 --output data/processed/live_acceptance/discovery_gate
apps/api/.venv/bin/python apps/api/scripts/build_prediction_dataset.py --start 2025-10-01T00:00:00Z --end 2025-10-29T00:00:00Z --feasibility --stations data/processed/live_acceptance/discovery_gate/selected_stations.json --retrospective-research --output data/processed/live_acceptance/real_gate
# Refuses to query full-period hours until the real gate passes.
apps/api/.venv/bin/python apps/api/scripts/audit_prediction_coverage.py --gate-directory data/processed/live_acceptance/real_gate
# Use the measured final selection and documented common start/end for a full build.
# --retrospective-research adds the separate research profile to default OPERATIONAL_V1.
apps/api/.venv/bin/python apps/api/scripts/build_prediction_dataset.py --start 2025-02-19T00:00:00Z --end 2026-01-01T00:00:00Z --stations data/processed/live_acceptance/final_selection/selected_stations.json --gate-directory data/processed/live_acceptance/real_gate_repeat --aq-availability-buffer-hours 72 --retrospective-research --output data/processed/live_acceptance/full_dataset
apps/api/.venv/bin/python apps/api/scripts/validate_prediction_dataset.py --output data/processed/live_acceptance/full_dataset --require-operational
apps/api/.venv/bin/python apps/api/scripts/validate_prediction_dataset.py --output data/processed/live_acceptance/real_gate --require-operational
apps/api/.venv/bin/python apps/api/scripts/probe_openaq_availability.py --stations data/processed/live_acceptance/discovery_gate/selected_stations.json
```

Keep OPENAQ_API_KEY and ADC server-side in ignored local configuration. Never commit keys, ADC caches or tokens. CI uses sanitized fakes only and never makes live OpenAQ/Earth Engine requests. Phase 2D remains a separate decision.
