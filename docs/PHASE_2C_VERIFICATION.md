# Phase 2C live data acceptance

Real extraction completed on **2026-09-14**; final artifact acceptance verified on **2026-09-16**. **Five real NCR stations, a shared 316-day window and both feature profiles are built and validated.** No Phase 2D training has begun. The operational contract remains conditional on prospective publication-lag and revision validation before serving.

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

## Full real dataset acceptance

The audited common window is **2025-02-19T00:00Z through 2026-01-01T00:00Z**, end exclusive: 316 days, 7,584 hours per station and **37,920 forecast origins**. The original full-year goal supported only one ≥80%-coverage station. The revised start follows the observed February source-series start, before inspecting labels or baselines. Require ≥80% usable PM hours and at least three adequately covered months, then maximize geographic spread. All five selected monitors use Asia/Kolkata and preserve :30 UTC interval ends.

| Location / sensor | Selected monitor | Provider | Latitude, longitude | Returned PM hours | Usable PM hours | Missing | Longest gap (h) | Final operational rows |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 8118 / 23534 | New Delhi | AirNow | 28.63576, 77.22445 | 7378 | 7370 | 2.82% | 44 | 6820 |
| 6978 / 12235196 | Knowledge Park - III, Greater Noida - UPPCB | CPCB | 28.47272, 77.482 | 7000 | 6319 | 16.68% | 67 | 487 |
| 10488 / 12235065 | Najafgarh, Delhi - DPCC | CPCB | 28.570173, 76.933762 | 7052 | 6412 | 15.45% | 62 | 541 |
| 10485 / 12235056 | Narela, Delhi - DPCC | CPCB | 28.822836, 77.101981 | 7207 | 6647 | 12.35% | 62 | 666 |
| 10919 / 12235770 | Sanjay Nagar, Ghaziabad - UPPCB | CPCB | 28.685382, 77.453839 | 7038 | 6246 | 17.64% | 62 | 412 |

Normalized source snapshots contain **176,657 all-pollutant hourly records**, including **36,483 PM2.5 records** (33,779 usable), plus **41,880 ERA5 station-hours**, all including warmup. In the output period, 35,675 PM records were returned and 32,994 are usable. These are normalized `/hours` records, not OpenAQ's underlying raw subhourly measurement counters. Each profile contains 37,920 origins. Operational minimal target+latest-input eligibility is **20,292** after purge; requiring the complete PM core leaves **8,926**. Research minimal regression eligibility is **21,774**; it is not deployment-safe.

### Real attrition

Each station excludes 792 warmup hours and 18 boundary-purge rows. Missing-future and buffer categories overlap; they are not additive. Buffer loss/recovery compares target+primary-input eligibility at zero versus 72 hours, keeping targets fixed. Core-feature counts precede target/purge filtering.

| Station ID | Complete PM core features | Valid six-hour targets | Missing future targets | Additional buffer loss | Buffer recovery | Missing 30-day reference | Final operational rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10485 | 1994 | 4392 | 3192 | 369 | 97 | 1230 | 666 |
| 10488 | 1694 | 4062 | 3522 | 438 | 108 | 2253 | 541 |
| 10919 | 1345 | 3675 | 3909 | 524 | 141 | 3605 | 412 |
| 6978 | 1629 | 3936 | 3648 | 490 | 118 | 2097 | 487 |
| 8118 | 7057 | 7239 | 345 | 143 | 18 | 0 | 6820 |

**Coverage bias is substantial:** New Delhi/AirNow supplies 6,820/8,926 (**76.41%**) of the operational rows. The four CPCB stations' complete operational origins occur only at local hours **14–18**, due to daily low-coverage gaps combined with strict input windows and six complete future targets. AirNow retains all 24 local hours. No QA threshold, gap filling or feature expansion was used to conceal this. Pooled metrics must not be presented as representative round-the-clock NCR performance. Full optional-feature completeness differs again (7,057/839/1,073/1,397/534 by the selected-station order); downstream feature selection must account for missing optional covariates.

### Profiles, target and frozen rule

The actual operational feature list is:

`pm25_latest_available`, `hour_of_day`, `day_of_week`, `month`, `weekend`, `pm25_lag_73h`, `pm25_lag_74h`, `pm25_lag_75h`, `pm25_lag_78h`, `pm25_lag_84h`, `pm25_lag_96h`, `pm25_rolling_mean_3h`, `pm25_rolling_mean_6h`, `pm25_rolling_mean_12h`, `pm25_rolling_std_6h`, `history_count_30d`, `trailing_30d_p85_pm25`, `trailing_30d_p90_pm25`, `trailing_30d_p95_pm25`, `co_ppb_lag_72h`, `co_ppb_lag_73h`, `no2_ppb_lag_72h`, `no2_ppb_lag_73h`, `o3_ug_m3_lag_72h`, `o3_ug_m3_lag_73h`, `pm10_ug_m3_lag_72h`, `pm10_ug_m3_lag_73h`, `so2_ppb_lag_72h`, `so2_ppb_lag_73h`.

Research adds the six ERA5 bands and wind speed/direction to unbuffered PM at t, lags 1/2/3/6/12/24, means 3/6/12/24, std 6/24, trailing-history/calendar and optional current/lag1 pollutants. Its exact list and excluded operational candidates are in each `feature_availability_manifest.json`; every entry records source, historical and assumed operational availability, buffer, deployment safety, reason and revision risk. Operational contains **no ERA5**. Calendar is deterministic; buffered AQ is conditionally usable; research AQ/weather cannot pass operational export.

Both continuous targets remain same-station **max/mean PM2.5 over t+1…t+6, µg/m³**, with all six hours required. With latest input t−72, these outcomes occur **73–78 hours after that measurement**. This is an honest but difficult forecasting setup, not a two-hour-fresh feed assumption.

The operational spike rule froze **p85 + 30% increase**, strictly positive worsening and ≥576/720 hours in a full trailing 30 days. Training candidates p85 with 20/25/30% produced 22.9011/22.3663/21.6532% positives; p90 gave 16.8233/16.4668/16.0454%; p95 gave 10.8266/10.7293/10.4376%. All used the same 6,170 training labels and the predefined closest-to-20% policy. Validation/test were inspected only after freezing. Regression remains primary.

| Split | Inclusive start UTC | Exclusive end UTC | Operational regression n | Spike labels n | Positive prevalence |
| --- | --- | --- | ---: | ---: | ---: |
| train | 2025-02-19 00:00 | 2025-10-01 00:00 | 6768 | 6170 | 21.653160% |
| validation | 2025-10-01 00:00 | 2025-11-01 00:00 | 763 | 704 | 62.073864% |
| test | 2025-11-01 00:00 | 2026-01-01 00:00 | 1395 | 1360 | 30.588235% |

The last six origin hours at each boundary are purged, **90 rows total**. All stations share boundaries; no shuffle. Validation prevalence shifts sharply and classification is weak; no thresholds were retuned. Adjacent six-hour outcomes overlap, so row counts are not independent sample sizes. The separate station-holdout manifest reserves **8118** by a fixed highest-lexicographic-ID rule, excludes it from future fitting, and requires refreezing any data-dependent spike rule using only remaining training stations. It is a plan, not a fitted holdout evaluation.

### Real naive baselines

Target is future six-hour maximum; MAE/RMSE are **µg/m³**. Persistence uses PM at t−72; recent mean uses six complete hours ending there. Both use the same complete operational rows. These are retrospective benchmarks under the availability assumption, not prospective skill claims.

| Split | n | Persistence MAE | Persistence RMSE | Recent-mean MAE | Recent-mean RMSE |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | 6768 | 29.767339 | 46.002078 | 29.502832 | 45.230232 |
| validation | 763 | 49.469725 | 67.262530 | 47.546265 | 66.165517 |
| test | 1395 | 114.183297 | 141.931249 | 111.544552 | 140.463770 |

Always-negative precision/recall/F1 are **0/0/0** in all splits, with zero precision denominator flagged. The current-high baseline compares the latest buffered PM against its frozen trailing percentile; it sees no future input.

| Split | Classification n | Current-high precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: |
| train | 6170 | 0.102041 | 0.052395 | 0.069238 |
| validation | 704 | 0.479751 | 0.352403 | 0.406332 |
| test | 1360 | 0.156716 | 0.100962 | 0.122807 |

Research-only regression uses unbuffered AQ and a different population; its better scores do not establish deployable benefit from weather (these naive baselines do not use weather). Research train/validation/test persistence MAE/RMSE are **19.268283/32.503178**, **29.219525/44.314868**, **61.392628/84.966350**; six-hour-mean MAE/RMSE **22.916988/37.418993**, **31.839663/46.296893**, **71.431642/94.330719**, with common n **11,478/1,389/2,740**. Separate research p85+20% labels have prevalence 17.8806/36.3687/18.3510%. Full per-station metrics and confusion counts remain in each profile's local `baseline_metrics.json`.

### ERA5 completeness, failures and performance

All 41,880 warmup-inclusive station-hours have temperature, dewpoint, pressure and u/v wind. Hourly precipitation retains **41,205**, with **675 negative packing values rejected** (1.61%); the other bands have no missing values. Native ranges: temperature 277.8234–316.8848 K, dewpoint 266.3408–301.1820 K, pressure 96,709.1641–99,799.1367 Pa, precipitation 0–0.0119985 m, u −6.9594–7.1623 m/s, v −5.1034–5.6892 m/s. Native source units are preserved. Research joins the preceding UTC analysis hour; wind formulas and unique station/hour keys passed validation.

The candidate audit used **841 HTTP attempts, 147 cache hits, 1,798.870 s**: 840 HTTP 200 responses and one HTTP 500 recovered by bounded retry; no 429. Remaining per-minute quota stayed **30–59/60**.

The initial full extraction wrote **365 successful OpenAQ response cache entries** and completed 38 new ERA5 batches before one transient weather extraction failure for October 17–24. The identical query passed the separately recorded retry (840 station-hours, 22.014 s), without changing bands, geometry, scale, QA or timeout. The initial failure cause was not retained precisely enough to call it a timeout. The initial failed run predates durable run counters, so **its exact OpenAQ attempt count is unavailable**; successful cache writes must not be relabeled as request attempts. Its externally recorded log span was 1,364.572 s. A prior five-station batch probe took 19.755 s. Across that probe, initial attempt, one retry and successful resumption, weather used **51 RPC attempts for 50 successful unique batches**.

The successful resumed build used **0 OpenAQ requests, 10 Earth Engine RPCs, 405 cache hits, 10 misses**, and **191.944 s total** (188.118 s preparation/source work, 0.729 s operational frame work; remainder includes research and serialization). Unique timestamped `runs/*.json` now persist sanitized request/cache counters in `finally` for successes and failures. Original extraction manifests and failure evidence are archived under ignored `extraction_completed/`; resumption does not erase them.

### Independent validation and reproducibility

Both profiles pass reconstruction, station isolation, native-hour alignment, train-only label selection, chronological ordering and split-purge checks. Strict operational validation passes the 72-hour cutoff and feature-availability contract. Research reports `operational_availability_pass=false` by design. An independent deterministic sample of **500 real rows** checked buffered PM against source snapshots and recomputed all six future targets; all passed. Weather uniqueness, UTC-hour phase and wind-speed reconstruction also passed. Historical publication verification remains false.

The authoritative local artifacts are `data/processed/live_acceptance/full_dataset/`, with research under `research_enriched_v1/`. Both contain Parquets, availability/source/dataset manifests, coverage, attrition, target analysis, split/holdout plan, baselines and validation. Monthly per-station/pollutant coverage is retained. The cache-only repeat on clean implementation commit `f27ce7b3e8f7a1ec71bbfe6187d7a9a5f03ac6c7` passed with **415 hits, zero misses, zero OpenAQ requests, zero Earth Engine RPCs and 48.723 s total**. Both profiles' normalized source Parquets, prediction-frame Parquets and feature-availability manifest SHA-256 hashes are identical to the completed extraction. `cache_reproduction.json` records the comparison; dataset manifests record a clean source tree. Documentation-only commits may follow without changing artifact-generating code.

## Completed NCR candidate audit

All 60 sensors with ≥90 days of metadata overlap were measured. They returned **377,821 hourly records**, of which **332,491** met QA. The 86 other inventoried PM2.5 sensors lacked that overlap and were not assigned invented hourly coverage. Thirty-five sensors meet the 80% coverage threshold in the 316-day common window, before the remaining selection checks. The full 2025 calendar year supports only one qualifying station.

Every candidate’s coordinates, provider, instrument, timezone, first/last metadata timestamps and sensor identity are preserved in local `coverage_2025/candidate_inventory.json`; monthly usable coverage and longest gaps are in `candidate_coverage.csv`. This compact table covers every measured sensor. Counts are actual `/hours` records, not metadata measurement counters.

| Location / sensor | Monitor | Returned 2025 hours | Usable 2025 hours | 2025 missing | Common-window missing | Longest 2025 gap, hours |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 17 / 12234787 | R K Puram, Delhi - DPCC | 6993 | 6310 | 27.97% | 16.84% | 1173 |
| 50 / 12234796 | Punjabi Bagh, Delhi - DPCC | 6837 | 6104 | 30.32% | 19.55% | 1173 |
| 235 / 12235610 | Anand Vihar, New Delhi - DPCC | 7057 | 6282 | 28.29% | 17.18% | 1175 |
| 301 / 14258988 | Vikas Sadan, Gurugram - HSPCB | 1958 | 1679 | 80.83% | 77.86% | 6560 |
| 5404 / 12234702 | Pusa, Delhi - IMD | 6109 | 4450 | 49.20% | 41.32% | 1304 |
| 5541 / 12234684 | Burari Crossing, New Delhi - IMD | 6319 | 5527 | 36.91% | 27.16% | 1173 |
| 5570 / 12234708 | Aya Nagar, New Delhi - IMD | 6362 | 5505 | 37.16% | 27.45% | 1173 |
| 5586 / 12234769 | Sirifort, Delhi - CPCB | 7216 | 6639 | 24.21% | 12.50% | 1173 |
| 5598 / 12235187 | Sector - 125, Noida, UP - UPPCB | 6815 | 6085 | 30.54% | 19.80% | 1173 |
| 5610 / 12234690 | North Campus, DU, Delhi - IMD | 6694 | 6014 | 31.35% | 20.74% | 1173 |
| 5613 / 12234753 | ITO, New Delhi - CPCB | 7196 | 6224 | 28.95% | 17.97% | 1173 |
| 5616 / 12234720 | Sector - 62, Noida, UP - IMD | 6532 | 5881 | 32.87% | 22.49% | 1173 |
| 5622 / 12234744 | NSIT Dwarka, Delhi - CPCB | 7108 | 6203 | 29.19% | 18.25% | 1173 |
| 5626 / 12234760 | DTU, New Delhi - CPCB | 7207 | 6613 | 24.51% | 12.84% | 1173 |
| 5627 / 12234678 | CRRI Mathura Road, New Delhi - IMD | 7019 | 6203 | 29.19% | 18.25% | 1173 |
| 5630 / 12234726 | Shadipur, Delhi - CPCB | 7105 | 6122 | 30.11% | 19.32% | 1173 |
| 5634 / 12234714 | Lodhi Road, New Delhi - IMD | 5454 | 4833 | 44.83% | 36.31% | 1457 |
| 5650 / 12234696 | IGI Airport (T3), Delhi - IMD | 5870 | 5223 | 40.38% | 31.17% | 1173 |
| 5665 / 12235160 | Vasundhara, Ghaziabad - UPPCB | 6819 | 5809 | 33.69% | 23.43% | 1173 |
| 6356 / 12235321 | Pusa, Delhi - DPCC | 7100 | 6499 | 25.81% | 14.35% | 1173 |
| 6358 / 12234778 | Mandir Marg, New Delhi - DPCC | 6951 | 5966 | 31.89% | 21.37% | 1173 |
| 6359 / 12234735 | IHBAS, Dilshad Garden,New Delhi - CPCB | 7066 | 5276 | 39.77% | 30.47% | 1173 |
| 6924 / 12235779 | Indirapuram, Ghaziabad - UPPCB | 6908 | 6182 | 29.43% | 18.53% | 1173 |
| 6929 / 12235047 | Major Dhyan Chand National Stadium, Delhi - DPCC | 7121 | 6496 | 25.84% | 14.39% | 1173 |
| 6931 / 12235020 | Dwarka-Sector 8, Delhi - DPCC | 7100 | 6480 | 26.03% | 14.60% | 1173 |
| 6932 / 12235698 | Alipur, Delhi - DPCC | 7093 | 6336 | 27.67% | 16.50% | 1173 |
| 6934 / 12235011 | Dr. Karni Singh Shooting Range, Delhi - DPCC | 7072 | 6458 | 26.28% | 14.89% | 1173 |
| 6936 / 14233904 | Arya Nagar, Bahadurgarh - HSPCB | 2086 | 1810 | 79.34% | 76.13% | 6490 |
| 6938 / 12235133 | Vivek Vihar, Delhi - DPCC | 6953 | 6294 | 28.15% | 17.05% | 1173 |
| 6953 / 14250045 | Sector-2 IMT, Manesar - HSPCB | 1970 | 1639 | 81.29% | 78.39% | 6537 |
| 6957 / 12235038 | Jawaharlal Nehru Stadium, Delhi - DPCC | 7009 | 6407 | 26.86% | 15.56% | 1173 |
| 6960 / 12235101 | Patparganj, Delhi - DPCC | 7096 | 6511 | 25.67% | 14.19% | 1173 |
| 6978 / 12235196 | Knowledge Park - III, Greater Noida - UPPCB | 7004 | 6322 | 27.83% | 16.68% | 1173 |
| 6980 / 12235951 | Sector-1, Noida - UPPCB | 7002 | 6364 | 27.35% | 16.13% | 1173 |
| 6986 / 12235935 | Knowledge Park - V, Greater Noida - UPPCB | 7225 | 6537 | 25.38% | 13.84% | 1173 |
| 6988 / 12235942 | Sector-116, Noida - UPPCB | 6438 | 5619 | 35.86% | 25.95% | 1173 |
| 7005 / 12235787 | Loni, Ghaziabad - UPPCB | 6411 | 5588 | 36.21% | 26.36% | 1173 |
| 8118 / 23534 | New Delhi | 8554 | 8436 | 3.70% | 2.82% | 82 |
| 8235 / 12235029 | Jahangirpuri, Delhi - DPCC | 7156 | 6048 | 30.96% | 20.29% | 1173 |
| 8239 / 12235074 | Okhla Phase-2, Delhi - DPCC | 7059 | 6429 | 26.61% | 15.27% | 1173 |
| 8365 / 12235083 | Nehru Nagar, Delhi - DPCC | 7195 | 6584 | 24.84% | 13.23% | 1173 |
| 8472 / 12235294 | Bawana, Delhi - DPCC | 7208 | 6624 | 24.38% | 12.70% | 1173 |
| 8475 / 12235110 | Sonia Vihar, Delhi - DPCC | 7104 | 6493 | 25.88% | 14.43% | 1173 |
| 8915 / 12235124 | Wazirpur, Delhi - DPCC | 7163 | 6580 | 24.89% | 13.28% | 1173 |
| 8917 / 12235002 | Ashok Vihar, Delhi - DPCC | 7154 | 6560 | 25.11% | 13.54% | 1173 |
| 10484 / 12235312 | Sri Aurobindo Marg, Delhi - DPCC | 6867 | 6230 | 28.88% | 17.89% | 1173 |
| 10485 / 12235056 | Narela, Delhi - DPCC | 7211 | 6650 | 24.09% | 12.35% | 1173 |
| 10486 / 12235303 | Mundka, Delhi - DPCC | 7087 | 6450 | 26.37% | 14.99% | 1173 |
| 10488 / 12235065 | Najafgarh, Delhi - DPCC | 7056 | 6415 | 26.77% | 15.45% | 1173 |
| 10820 / 12236236 | Sector 30, Faridabad - HSPCB | 1155 | 660 | 92.47% | 91.34% | 5063 |
| 10825 / 12236259 | Sector-51, Gurugram - HSPCB | 2985 | 2544 | 70.96% | 66.50% | 3816 |
| 10831 / 12235092 | Rohini, Delhi - DPCC | 7213 | 6246 | 28.70% | 17.68% | 1173 |
| 10900 / 12236251 | Teri Gram, Gurugram - HSPCB | 2249 | 1247 | 85.76% | 83.58% | 4298 |
| 10908 / 12236245 | Sector 11, Faridabad - HSPCB | 2774 | 2376 | 72.88% | 68.71% | 4349 |
| 10919 / 12235770 | Sanjay Nagar, Ghaziabad - UPPCB | 7042 | 6249 | 28.66% | 17.64% | 1173 |
| 10920 / 12236227 | New Industrial Town, Faridabad - HSPCB | 3018 | 2616 | 70.14% | 65.55% | 4256 |
| 10921 / 12235707 | NISE Gwal Pahari, Gurugram - IMD | 6694 | 5810 | 33.68% | 23.43% | 1173 |
| 11603 / 12236361 | Chandni Chowk, Delhi - IITM | 6584 | 4399 | 49.78% | 42.00% | 1578 |
| 11607 / 12236376 | Lodhi Road, Delhi - IITM | 6433 | 4647 | 46.95% | 38.77% | 1173 |
| 3410004 / 12238725 | Amity University, Panchgaon - IITM | 6585 | 5708 | 34.84% | 24.78% | 1173 |

The common-window selection keeps the earliest fully supported day within the preferred audited year, **February 19**, rather than accepting the shared January/early-February absence. It is not a claim that no longer series exists outside the audited 2025 period. QA thresholds were unchanged; label prevalence and baseline scores did not influence the date choice.

## Automated verification

Current local checks: **368 backend tests passed**, 2 existing dependency warnings, 19.89 seconds; **26 browser tests passed**, 29.0 seconds. Frontend lint/typecheck/production build passed. OpenAPI export and generated frontend types have no diff. Docker build/start/health passed with the existing read-only ADC override and loopback bindings. Ruff passes for all 61 Python files, and the final diff has no whitespace errors. On September 16 local time, both Docker services remain healthy. The final source, compiled-frontend and generated-data secret scan passed: **3,386 files, zero findings**. Large source/data artifacts remain ignored. GitHub CI runs backend, frontend, browser/Docker and secret checks on push and PR events; the exact final-head results are attached to [PR #5](https://github.com/aadiandrj-prog/airshedos/pull/5/checks), and must remain green before merge. CI receives no provider credentials and uses fakes only.

## Synthetic smoke artifacts — not monitoring data

Three clearly named synthetic test locations, 2025-01-01T00:00:00Z to 2025-04-01T00:00:00Z (90 days), plus 30 warmup days. Generated 8,640 AQ-shaped rows including warmup, 8,613 usable synthetic PM2.5 values, 6,480 output station-hour rows, and 6,279 regression-eligible rows after split purging. PM2.5 missingness in the output is 0.324074%. Synthetic weather is fully populated; that is not evidence of real ERA5 completeness.

Artifacts remain under ignored `data/processed/fixture_v1/`: all three Parquet files, dataset/source/split manifests, coverage CSV, target analysis, baseline metrics and leakage report. No generated data is committed. The deterministic generator and small request-shaped fixtures are code in the repository; all locations and values are artificial.

Frame construction and validation timing recorded in this run: **0.159 seconds**, excluding artifact serialization. These synthetic timings do not measure the real extraction reported above. The fixture command made **0 OpenAQ requests and 0 Earth Engine RPCs**. A separate full pipeline test exercised fake discovery, ingestion and 18 simulated weather batches; a repeat made no additional simulated requests.

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

Branch `codex/phase-2c-prediction-dataset`, [draft PR #5](https://github.com/aadiandrj-prog/airshedos/pull/5), stacked on Phase 2B. No automatic merge. **READY FOR PHASE 2D** for controlled offline regression work under the documented conditional availability contract, subject to green final-head CI. This is not authorization to begin training in this task or evidence of readiness to serve predictions. No model fitting, Vertex jobs, new source, forecast service or forecast UI changes have been made.

## Remaining limitations and next-phase recommendation

Before any serving decision, validate publication lag and revisions prospectively, enforce live stale/missing-input behavior, and review the conditional feature manifest. Historical observations cannot prove what was published at issuance. The single September 14 first-seen snapshot does not establish a stable 72-hour guarantee. No newly requested multi-day probe was run during resumption.

A separate Phase 2D should begin with the operational PM-only regression population and explicit station/hour-stratified evaluation, comparing against the recorded baselines. Review AirNow dominance, CPCB afternoon-only eligibility, overlapping outcomes, autumn/winter error and class-prevalence shift before interpreting pooled scores. Keep retrospective ERA5 ablations isolated. Missing optional inputs require an explicit later feature policy. The holdout plan is available but not evaluated. Exact OpenAQ attempt accounting for the initial interrupted extraction remains unavailable; successful-response and resumed-run counts are reported honestly above.

No source was added to fill coverage, no QA was lowered, no synthetic values filled real gaps, and no Phase 2D model, Vertex job, endpoint or forecast UI change was introduced.
