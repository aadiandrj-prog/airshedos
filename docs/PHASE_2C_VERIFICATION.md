# Phase 2C verification — implementation complete, live gates pending

Verified 2026-09-14. User decision: **“Proceed with fixtures; live extraction stays pending.”** This report records synthetic verification, not historical NCR results. Phase 2C cannot yet be marked fully accepted or ready for Phase 2D.

## Real-data acceptance status

| Requirement | Result |
| --- | --- |
| Geographic scope | Core Delhi–NCR study box; objective discovery implemented |
| OpenAQ authentication/live hourly extraction | Pending; OPENAQ_API_KEY not configured |
| Real candidate locations inspected | 0; pending live discovery |
| Real selected stations and reasons | Pending measured common-period coverage; none invented |
| Intended historical range | Complete 2025 UTC calendar year, or documented common range >=90 days after coverage inspection |
| Real raw PM2.5 observations / usable rows / missingness | Pending extraction |
| ERA5 source implementation | Six native bands and wind derivatives; batched adapter verified with fakes, not a live Phase 2C query |
| Multi-week two-station feasibility gate | Pending; synthetic artifacts cannot unlock full CLI build |
| Full practical dataset build | Pending real feasibility and station-selection gates |
| Real spike rule, class prevalence and baseline metrics | Pending; synthetic figures below are not estimates |
| As-of publication availability | Explicitly fails: current-hour ERA5 was released later; OpenAQ first availability/revision history unverified |
| Vertex training / deployed predictions | Not started |

No OpenAQ or ERA5 remote extraction request was made for this fixture verification. Previous Earth Engine authentication verification does not prove this new historical extractor works against real source payloads. The live gate must check interval alignment, metadata, QA coverage and ERA5 extraction expression before making that claim.

## Offline implementation

OpenAQ v3 hourly means, bounded pagination/retries, source/query caches, duplicate checks and native units; measured coverage reports and geographic spread after coverage qualification; seven-day all-station ERA5 batching; station-isolated exact-hour lags and trailing windows; complete six-hour targets; training-only spike selection; chronological splits with target purging; naive baselines; checksummed Parquet and manifests. See [the complete data contract](PREDICTION_DATASET.md) for source documentation, feature definitions, setup and reproduction commands.

Historical fires are explicitly deferred: the proposed NOAA-20 daily raster lacks exact within-day acquisition times for safe hourly windows. A separate exact-event window helper is tested but unused by the frame. Sentinel-5P is deferred as an asynchronous optional ablation. Existing environmental, satellite, citizen and corroboration runtime files are unchanged.

## Synthetic smoke artifacts — not monitoring data

Three clearly named synthetic test locations, 2025-01-01T00:00:00Z to 2025-04-01T00:00:00Z (90 days), plus 30 warmup days. Generated 8,640 AQ-shaped rows including warmup, 8,613 usable synthetic PM2.5 values, 6,480 output station-hour rows, and 6,279 regression-eligible rows after split purging. PM2.5 missingness in the output is 0.324074%. Synthetic weather is fully populated; that is not evidence of real ERA5 completeness.

Artifacts remain under ignored `data/processed/fixture_v1/`: all three Parquet files, dataset/source/split manifests, coverage CSV, target analysis, baseline metrics and leakage report. No generated data is committed. The deterministic generator and small request-shaped fixtures are code in the repository; all locations and values are artificial.

Frame construction and validation timing recorded in this run: **0.168 seconds**, excluding artifact serialization. Live build duration/cost is unknown. The fixture command made **0 OpenAQ requests and 0 Earth Engine RPCs**. A separate full pipeline test exercised fake discovery, ingestion and 18 simulated weather batches; a repeat made no additional simulated requests.

### Targets and features

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

## Verification results

- Dataset tests: **62 passed** (including ingestion-to-artifact fake-source integration and cache reuse).
- Full backend regression: **341 passed, 2 pre-existing dependency warnings**, 15.81 seconds; includes all 279 prior product tests.
- Python lint/format: **pass**, 56 Python files formatted.
- Frontend lint/typecheck/production build: **pass**.
- OpenAPI export + frontend type generation: **pass, no diff**.
- Dataset fixture build, validation and baseline CLI: **pass**. Source hashes and artifact round-trip validated.
- Strict `--require-operational`: **expected failure**, exit 2. Availability is not waived or fabricated.
- Browser: **26 passed in 29.1 seconds** after resuming Docker and starting the app.
- Docker: **build/start/health passed**; API and web healthy on loopback ports 8000/3000, frontend HTTP 200, existing ADC mount confirmed read-only.
- Secret scan: **pass, 0 findings** across Git-visible files, compiled frontend and all generated fixture artifacts; **1,714 files scanned**.
- GitHub CI: pending Phase 2C push.

Leakage tests cover independent numerical lag/rolling/future-target expectations, future-input perturbation invariance, station isolation, missing future hours, minimum trailing history, training-only sensitivity selection, explicit target exclusion, chronological alignment/purge, exact fire acquisition/availability windows, deliberate feature/target corruption and checksum tampering. No live calls are permitted in CI.

First browser attempts encountered `ERR_CONNECTION_REFUSED`: Docker Desktop had been manually paused. No product change was made in response. The resumed run passed all 26 tests. PyArrow emitted harmless sandbox CPU-cache-probe messages during local artifact reads; validation and baseline commands exited successfully. Pinning NumPy below 2.4 avoids pandas 2.x timedelta deprecation noise; no warning suppression was added.

## Git and remaining gates

Branch: `codex/phase-2c-prediction-dataset`, based on verified Phase 2B `fdfb79300c05576df93b1ae7a4f0cb25526f4893`. Phase 2A PR #3 and Phase 2B PR #4 remain open; this change is stacked against the Phase 2B branch. No automatic merge is performed. Commit and PR will be recorded after final checks.

**Recommendation: do not start Phase 2D yet.** Complete OpenAQ setup, real 2–4-week two-station feasibility, real measured station selection, full practical common-period dataset and real baselines. Separately resolve operational publication availability with an as-of source design and prospective validation. Scientific limits remain: NCR specificity, monitors are not every street, coarse reanalysis, no causal source attribution, and a heuristic spike label that is neither regulatory nor epidemiological. No production training, forecast service/UI, new Gemini pass, database or warehouse was added.
