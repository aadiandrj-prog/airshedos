# Phase 2C live data acceptance

Verified work in progress on **2026-09-14**. The latest user instruction authorizes real OpenAQ extraction using the backend key. The earlier fixture-only decision is superseded. **Live feasibility passes; the 60-sensor coverage audit is complete and common-period artifact acceptance is running. No Phase 2D training has begun.**

## Real NCR evidence

OpenAQ v3 authentication passed (HTTP 200). The NCR study-box inventory returned **95 stationary PM2.5 monitor locations and 146 PM2.5 sensors**. Sixty sensors have at least 90 days of metadata overlap with 2025 and were assessed using actual hourly resources; expired duplicates are recorded separately and not blended. Metadata counters are not hourly counts. A bounded pagination test returned **50 + 45 distinct locations**, with no duplicate IDs. Response quota headers were inspected without recording request credentials.

Authentication took 1.533 seconds and one request. Sensor inventory and the separate pagination check used 148 requests over 294.784 seconds. Initial response headers reported limit 60, remaining 59, used 1, reset 60. Full candidate and normalized coverage artifacts are under ignored `data/processed/live_acceptance/` and `coverage_2025/`.

### Genuine two-station feasibility

The 28-day window is **2025-10-01T00:00:00Z through 2025-10-29T00:00:00Z**, plus 33 days of operational warmup. Twelve locations were measured for the bounded selection; coverage qualification precedes geographic spread. These are gate stations, not a predetermined final NCR selection.

| Gate station | Location / PM2.5 sensor | Coordinates | Usable PM hours in requested window | Complete operational rows |
| --- | --- | --- | ---: | ---: |
| Sirifort, Delhi - CPCB | 5586 / 12234769 | 28.5504249, 77.2159377 | 89.29% | 87 |
| Burari Crossing, New Delhi - IMD | 5541 / 12234684 | 28.7256504, 77.2011573 | 85.57% | 50 |

Both use Asia/Kolkata and Government Monitor metadata; provider is CPCB. Their nearest separation is about 19.5 km. The resulting frame has **1,344 station-hour origins, 699 minimal regression-eligible rows after purge, and 137 complete operational PM feature/target rows**. These counts are deliberately distinct. The latter excludes missing PM lags/rolling inputs and purged rows; optional covariate completeness and percentile history are separate diagnostics.

The original AQ extraction used **46 OpenAQ requests**. The corrected weather extraction used **9 Earth Engine RPCs**, 46 AQ cache hits, 129.043 seconds of source/build preparation plus 0.160 seconds of frame work. It returned **2,928 weather station-hours** including warmup. All temperature/dewpoint/pressure/wind values were present; each station retained **98.019% precipitation values** after rejecting negative packing artifacts. Wind derivatives are computed from the actual native u/v values. The successful repeat used **55 cache hits, zero OpenAQ requests, zero Earth Engine RPCs**, 1.674 seconds of preparation and 0.122 seconds of frame work. Both profiles reused identical source snapshots.

### Problems discovered and resolved before full extraction

1. Actual CPCB hourly intervals end at **:30 UTC**. The old top-of-UTC-hour assumption would reject valid local-hour observations. The grid now preserves their exact interval end and consistent phase. A research row at 12:30 uses ERA5 at 12:00; it never joins a future weather analysis.
2. The source reports recurrent **50% coverage** at 19:30 UTC / 01:00 local time. For example, Sirifort values 34.0, 20.8 and 56.9 µg/m³ at that hour on October 1, 2 and 3 remain unusable under the unchanged ≥75% rule. Neither gate series has a complete valid 24-hour run. The operational profile excludes its unavailable 24-hour mean/std candidates; research preserves their missingness. No QA was weakened, and no interpolation was added.
3. The original ERA5 `reduceRegions` point expression returned rows containing IDs/timestamps but **no band values**. Thus the first extraction was not a valid weather gate, despite successful authentication. Direct same-image/same-point diagnostics showed `reduceRegion` returned all six native values. Mapping that reducer server-side fixed extraction while retaining one RPC per multi-station seven-day batch. Explicit CRS and native-transform tests did not fix the original expression. Old null responses remain in the diagnostic cache; the corrected method has a distinct cache query version. An all-null extraction now fails, and full extraction requires real band completeness.

Sanitized expression diagnostics are `era5_expression_diagnostic.json` and `era5_expression_alternatives.json`. At Sirifort on **2025-10-01T00:00Z**, the verified native sample is temperature **297.5831298828125 K**, dewpoint **297.0349578857422 K**, pressure **97713.16015625 Pa**, hourly precipitation **4.470348358154297e-07 m**, u **−0.8878936767578125 m/s**, v **−0.8720283508300781 m/s**. It is regional reanalysis, not a ground weather measurement. See the [official collection](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY) and [reduction API](https://developers.google.com/earth-engine/apidocs/ee-image-reduceregion).

### Availability contract

**OPERATIONAL_V1** excludes ERA5 and uses AQ no later than t−buffer. **RESEARCH_ENRICHED_V1** is marked **NOT DEPLOYMENT-SAFE AS CURRENTLY SOURCED**. Every profile has a checksummed feature-availability manifest. Safe AQ flags are explicitly conditional; operational export requires deliberate acknowledgment. Known revisions/late publication are excluded from inputs; unknown revisions remain a limitation.

The initial prospective poll at **2026-09-14T07:44:46.035948Z** found both gate feeds latest at **2026-09-11T10:30Z**, age **69.246121 hours**. The default configurable buffer is **72 hours**, chosen from observed staleness rather than predictive accuracy. A 1h/2h guarantee was not supported. Two fresh requests recorded 96 hourly rows per station. No revisions were observed in this single poll, which cannot prove absence of revisions. First-seen time is a left-censored upper bound, not historical publication time. Follow-up prospective validation remains necessary before serving; no days-long study or automation was started.

Targets stay anchored at forecast origin **t+1…t+6** despite the 72-hour input buffer. All six observed PM hours are mandatory. Chronological splits, purging, future-perturbation invariance, manifest consistency and availability-cutoff checks pass for the real gate. Passing availability means enforcement of the stated conditional assumption, not proof of historical release timing.

### Remaining live acceptance work

The completed audit used **841 requests, 147 cache hits and 1,798.870 seconds**. Only AirNow location 8118 qualifies for the full calendar year. The earliest supported common start within the audited year is **2025-02-19T00:00Z**, ending **2026-01-01T00:00Z** (316 days). Five stations qualify: 8118 New Delhi (97.18%), 6978 Knowledge Park III (83.32%), 10488 Najafgarh (84.55%), 10485 Narela (87.65%) and 10919 Sanjay Nagar (82.36%). Quality qualification precedes geographic spread. Real full-period attrition, the train-only spike rule, prevalence, baselines and station holdout remain pending the full build. No synthetic figures below are substituted for these results. Full year extraction was held until the corrected feasibility gate passed.

## Automated verification

Current local checks: **366 backend tests passed**, 2 existing dependency warnings, 18.51 seconds; **26 browser tests passed**, 29.0 seconds. Frontend lint/typecheck/production build passed. OpenAPI export and generated frontend types have no diff. Docker build/start/health passed with the existing read-only ADC override and loopback bindings. Final checks and secret scan will be repeated after remaining code/artifact work; remote CI still refers to the previous committed offline baseline until this update is pushed.

## Synthetic smoke artifacts — not monitoring data

Three clearly named synthetic test locations, 2025-01-01T00:00:00Z to 2025-04-01T00:00:00Z (90 days), plus 30 warmup days. Generated 8,640 AQ-shaped rows including warmup, 8,613 usable synthetic PM2.5 values, 6,480 output station-hour rows, and 6,279 regression-eligible rows after split purging. PM2.5 missingness in the output is 0.324074%. Synthetic weather is fully populated; that is not evidence of real ERA5 completeness.

Artifacts remain under ignored `data/processed/fixture_v1/`: all three Parquet files, dataset/source/split manifests, coverage CSV, target analysis, baseline metrics and leakage report. No generated data is committed. The deterministic generator and small request-shaped fixtures are code in the repository; all locations and values are artificial.

Frame construction and validation timing recorded in this run: **0.159 seconds**, excluding artifact serialization. Live build duration/cost is unknown. The fixture command made **0 OpenAQ requests and 0 Earth Engine RPCs**. A separate full pipeline test exercised fake discovery, ingestion and 18 simulated weather batches; a repeat made no additional simulated requests.

### Synthetic research targets and features

Primary targets are same-station future max and mean PM2.5 over t+1…t+6, requiring all six hours, in µg/m³. PM2.5 current/lags 1,2,3,6,12,24; trailing means 3,6,12,24 and population std 6,24; 30-day history count/percentiles; station-local calendar; six ERA5 bands plus wind speed/direction. Optional pollutant current/lag columns preserve gas units. There are no fire or satellite input columns in this version.

Synthetic training selected **p85, 20% relative increase**, plus strictly positive worsening, from the predefined training-only grid. At least 576 observed hours in a full 30-day trailing window are required. This synthetic selection is not the final real-data rule.

| Synthetic split | Label count | Positive prevalence |
| --- | ---: | ---: |
| train | 4413 | 0.193293 |
| validation | 933 | 0.201501 |
| test | 933 | 0.187567 |

### Exact synthetic chronological boundaries

| Split | Start inclusive UTC | End exclusive UTC before purge |
| --- | --- | --- |
| train | 2025-01-01T00:00:00+00:00 | 2025-03-05T00:00:00+00:00 |
| validation | 2025-03-05T00:00:00+00:00 | 2025-03-18T12:00:00+00:00 |
| test | 2025-03-18T12:00:00+00:00 | 2025-04-01T00:00:00+00:00 |

Last six origin hours in each split are purged: 54 rows across three stations/three boundaries. All stations share boundaries. No shuffle, learned normalization, imputation or model fitting. Station holdout is a documented plan only.

### Synthetic regression calculation checks

MAE/RMSE units: µg/m³. Both methods use the same rows with current PM2.5 and a complete six-hour rolling mean.

| Split | Common n | Persistence MAE | Persistence RMSE | Recent mean MAE | Recent mean RMSE |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | 4338 | 18.222401 | 24.561630 | 26.247529 | 31.475383 |
| validation | 918 | 18.636695 | 25.469799 | 26.615653 | 32.191981 |
| test | 918 | 18.583046 | 25.050552 | 27.054039 | 32.405683 |

### Synthetic classification calculation checks

Always-negative precision/recall/F1 are 0 in all splits; zero precision denominator is explicitly flagged. Current-high means current PM2.5 >= the frozen trailing percentile, independent of future measurements.

| Split | Current-high precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| train | 0.066563 | 0.050410 | 0.057372 |
| validation | 0.092199 | 0.069149 | 0.079027 |
| test | 0.072464 | 0.057143 | 0.063898 |

## Git and decision

Branch `codex/phase-2c-prediction-dataset`, [draft PR #5](https://github.com/aadiandrj-prog/airshedos/pull/5), stacked on Phase 2B. No automatic merge. **NOT READY FOR PHASE 2D while full real-data acceptance remains incomplete.** No model fitting, Vertex jobs, new source, forecast service or forecast UI changes have been made.
