# Phase 2D verification — MODEL_NOT_ACCEPTED

Local model selection completed on **2026-09-16** (Asia/Kolkata). **None of the predeclared candidates beat the October baseline gates.** The explicit no-go branch of the brief applies: stop model selection, preserve the rejection, and do not open November–December to find a winner. This is a valid negative scientific result, not a trained model ready for integration.

## Dataset, isolation and exact experiment

The real `prediction_dataset_v2` source and availability artifacts were SHA-256 verified against the Phase 2C dataset contract. The operational frame has 8,926 eligible rows; **6,768 train and 763 October validation rows** entered modelling. The known Phase 2C test population is 1,395 rows, but **zero candidate-model test rows were evaluated**. Source-byte hash checks do not deserialize test records. The tuner receives separate train/validation Parquets produced using explicit Parquet split filters. It never receives a test frame or test metrics for selection.

Model experiment version: `prediction_model_v1`. Predeclared policy and all modelling code were committed at **`612dd8683212c4a36781ba98b711b5f90698b5e4` before training**. The policy hash is `3e2168b125af05a2f30f803a98fb3cf8e24dff329ac43ce48e6cded9b2ef449e`. The frozen rejection timestamp is **2026-09-15T23:37:50.039040+00:00**. Later changes only improve rejection handling, regression checks and documentation; the search and thresholds were not changed or rerun to obtain a winner.

| Population | 10485 | 10488 | 10919 | 6978 | 8118 | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 500 | 433 | 301 | 356 | 5178 | 6768 |
| October validation | 68 | 38 | 18 | 66 | 573 | 763 |

Train spans 2025-02-19T00:00Z to 2025-10-01T00:00Z. October validation ends 2025-11-01T00:00Z; November–December remains locked. All boundaries are exclusive on the right, with six-hour target-overlap purging and no shuffle.

| CV fold | Fit start UTC | Fit end UTC | Score end UTC | Fit rows | Score rows |
| --- | --- | --- | --- | ---: | ---: |
| 1 | 2025-02-19T00:00:00Z | 2025-06-01T00:00:00Z | 2025-07-01T00:00:00Z | 3054 | 888 |
| 2 | 2025-02-19T00:00:00Z | 2025-07-01T00:00:00Z | 2025-08-01T00:00:00Z | 3948 | 996 |
| 3 | 2025-02-19T00:00:00Z | 2025-08-01T00:00:00Z | 2025-10-01T00:00:00Z | 4950 | 1812 |

Each score block starts at the fit end. Fitting target-window ends must be strictly before the score boundary; scoring target ends must be strictly before the next boundary. Scaling, imputation, sample weights and high-PM thresholds use only that fold's fit population. No early stopping, random validation split, target imputation, station feature or target encoding.

## Bounded search and validation candidates

Three families × two feature policies × two weighting policies × two target transforms × two parameter settings = **48 CV configurations / 144 fits**, followed by **12 serious October fits**. CV chooses parameters and raw/log1p transform within each family/subset/weight policy, using mean fold macro-station MAE. October then compares those 12 candidates. All 12 CV choices favored log1p; it was not imposed in advance. Raw-target results remain in the complete CV evidence. Log predictions were inverse-transformed to µg/m³ before metrics; negative predictions were clipped to zero without positive capping. All twelve serious October candidates recorded zero clipped predictions.

Ridge α={10,100}, median imputation with missingness indicators and weighted training-only standardization. Histogram gradient boosting uses 150 iterations, learning rate .05, leaves {7,15}, minimum leaf samples 30, L2=10, no early stopping. XGBoost uses 150 trees, learning rate .05, depth {2,4}, minimum child weight 10, lambda 10, row/column subsampling .8, CPU histogram method. Fixed seed 42 and one compute thread. CORE_PM has 19 columns; EXTENDED has 29, adding buffered CO/NO2/O3/PM10/SO2. All candidates use the same rows; optional missing values never delete rows. Station-balanced weights use fitting counts only and average to one.

| Candidate | Subset | Weighting | Chosen parameter | CV macro MAE | October macro MAE | Pooled MAE | Pooled RMSE | Bias | Go |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| ridge | CORE_PM | unweighted | alpha=10.0 | 17.026792 | 71.344796 | 68.612816 | 90.996019 | -67.914539 | NO |
| ridge | CORE_PM | station_balanced | alpha=10.0 | 17.372901 | 61.960955 | 60.137483 | 81.899200 | -59.050765 | NO |
| ridge | OPERATIONAL_EXTENDED | unweighted | alpha=100.0 | 16.760687 | 70.973003 | 68.765917 | 91.092180 | -68.012756 | NO |
| ridge | OPERATIONAL_EXTENDED | station_balanced | alpha=100.0 | 17.086352 | 62.160784 | 61.140199 | 83.365306 | -59.907557 | NO |
| hist_gradient_boosting | CORE_PM | unweighted | max_leaf_nodes=7 | 17.781143 | 64.845993 | 66.566653 | 89.675607 | -65.558684 | NO |
| hist_gradient_boosting | CORE_PM | station_balanced | max_leaf_nodes=7 | 17.404610 | 64.473164 | 63.978785 | 87.691631 | -62.782227 | NO |
| hist_gradient_boosting | OPERATIONAL_EXTENDED | unweighted | max_leaf_nodes=7 | 17.614424 | 65.793937 | 67.327037 | 90.411975 | -66.290513 | NO |
| hist_gradient_boosting | OPERATIONAL_EXTENDED | station_balanced | max_leaf_nodes=7 | 16.568278 | 64.613624 | 64.484265 | 87.999896 | -63.138594 | NO |
| xgboost | CORE_PM | unweighted | max_depth=2 | 17.694069 | 62.360673 | 62.693515 | 84.784697 | -61.254469 | NO |
| xgboost | CORE_PM | station_balanced | max_depth=2 | 17.102729 | 61.929456 | 60.473177 | 83.711405 | -58.478716 | NO |
| xgboost | OPERATIONAL_EXTENDED | unweighted | max_depth=2 | 17.493180 | 63.489021 | 63.935170 | 86.411702 | -62.548405 | NO |
| xgboost | OPERATIONAL_EXTENDED | station_balanced | max_depth=2 | 16.754356 | 62.406404 | 62.173209 | 85.460906 | -60.248472 | NO |

Exact baseline metrics were reproduced from Phase 2C artifacts rather than hardcoded. Reference selection was predeclared as the lower October macro-station MAE of persistence and six-hour recent mean on identical rows.

| October baseline | Macro-station MAE | Macro-station RMSE | Pooled MAE | Pooled RMSE | Bias |
| --- | ---: | ---: | ---: | ---: | ---: |
| persistence | 59.873076 | 74.670559 | 49.469725 | 67.262530 | -40.375098 |
| recent_mean_6h | 53.926835 | 69.506254 | 47.546265 | 66.165517 | -38.658541 |

The predeclared gate required ≥2% improvement in validation macro MAE, pooled MAE no more than 2% worse, ≥60% of stations improving, and no station MAE exceeding baseline×1.25+2 µg/m³. All candidates failed the macro, pooled, station-catastrophe and majority-improvement checks. The strongest rejected model is **station-balanced CORE_PM XGBoost, depth 2, log1p**. Its macro MAE is **61.929456**, versus **53.926835** for the recent-mean baseline; pooled MAE **60.473177**, versus **47.546265**. It is a diagnostic comparison, not a selected winner.

Station weighting helped relative to the corresponding unweighted candidates but did not meet the baseline. Optional pollutants did not improve the best XGBoost or balanced Ridge October result. This bounded experiment does not prove that every possible model or feature policy will fail. No additional search was launched after rejection.

## Station, hour, pollution and bias evidence

The tables below describe the strongest **rejected** candidate. Aggregated slices for **every serious candidate**, including each station, local hour, month, target band, clipping count and spike confusion matrix, are committed in [the full metrics evidence](evidence/phase2d_validation_metrics.json). All quantities are retrospective and conditional on assumed availability; residual = prediction−actual.

| Station | n | MAE | RMSE | Bias | Recent-mean MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| 10485 | 68 | 62.991272 | 79.103304 | -62.239365 | 53.158088 |
| 10488 | 38 | 42.415523 | 53.993232 | -41.161037 | 38.180263 |
| 10919 | 18 | 98.834322 | 112.129054 | -98.834322 | 90.728704 |
| 6978 | 66 | 43.256238 | 59.677411 | -39.093349 | 40.625000 |
| 8118 | 573 | 62.149927 | 87.121455 | -60.146048 | 46.942118 |

| Local hour | n | MAE | RMSE |
| --- | ---: | ---: | ---: |
| 0 | 23 | 74.456282 | 107.654215 |
| 1 | 23 | 75.139355 | 107.426977 |
| 2 | 23 | 75.284989 | 106.761109 |
| 3 | 23 | 75.027577 | 107.125387 |
| 4 | 22 | 73.379355 | 101.606686 |
| 5 | 22 | 69.689791 | 95.208252 |
| 6 | 24 | 64.523449 | 87.321768 |
| 7 | 24 | 63.478302 | 85.604378 |
| 8 | 25 | 62.869649 | 83.659837 |
| 9 | 26 | 67.718565 | 92.742694 |
| 10 | 25 | 54.609248 | 73.441169 |
| 11 | 25 | 50.464149 | 66.635815 |
| 12 | 25 | 42.692512 | 56.292480 |
| 13 | 24 | 38.755332 | 49.243856 |
| 14 | 60 | 41.137218 | 53.314087 |
| 15 | 66 | 47.438962 | 58.876951 |
| 16 | 63 | 57.319697 | 77.315315 |
| 17 | 60 | 63.826288 | 88.377740 |
| 18 | 59 | 61.848381 | 79.167313 |
| 19 | 23 | 59.367013 | 77.197516 |
| 20 | 24 | 64.625105 | 84.126759 |
| 21 | 24 | 72.235161 | 100.219404 |
| 22 | 25 | 75.378215 | 105.723893 |
| 23 | 25 | 73.734479 | 105.764781 |

Training target p50/p90/p99 were frozen at **49 / 112.3 / 198 µg/m³**. The same bands were used for every October candidate. High pollution is strictly above training p90. No threshold was selected after inspecting candidate errors.

| Target band | n | MAE | RMSE | Bias | Underprediction rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| lower | 157 | 8.246968 | 10.311485 | 1.445856 | 0.490446 |
| medium | 363 | 40.429141 | 43.365841 | -40.429141 | 1.000000 |
| high | 172 | 91.121171 | 93.514040 | -91.121171 | 1.000000 |
| extreme | 71 | 204.192114 | 210.409726 | -204.192114 | 1.000000 |

Above training p90: **n=243, MAE=124.158360, bias=-124.158360, underprediction rate=1.000000**. Negative bias explicitly indicates missed high-PM magnitudes. October mean bias is -58.478716. The strong degradation from training-only CV to October is evidence of distribution shift; November–December was deliberately not opened.

Derived spike interpretation uses the unchanged Phase 2C p85 +30% +strict worsening rule. For this rejected candidate: **n=704, precision=1.000000, recall=0.018307, F1=0.035955; TP=8, FP=0, FN=429, TN=267**. Missing percentile/label rows are excluded from classification only. No separate classifier, threshold tuning or probability output.

## Freeze, no-test audit and deferred downstream gates

`data/models/phase2d_v1/model_selection_decision.json` freezes **NO_MODEL_ACCEPTED** with policy/source hashes, git commit, thresholds, baseline comparison and time. [Committed decision summary](evidence/phase2d_decision.json) records the result. `test_access_audit.json` records **zero candidate test evaluations**; no dataset test reservation or test predictions exist. The rejected-decision guard is tested to fail before any Parquet read. A qualifying run would reserve test access atomically, verify immutable artifact hashes and prohibit retuning/repeated access; that branch was not used on this dataset.

The explicit no-go instruction takes precedence over downstream acceptance items that presuppose a chosen model. Therefore no final model bundle/input contract, final test metrics, station-8118 fitted holdout, research-enriched ablation, selected-model feature importance, three-seed finalist study or Vertex parity claim is produced. None is marked passed. The code contains guarded local evaluation/diagnostic paths for a genuinely qualifying future experiment; this report does not claim those paths were exercised on real data. Research never replaced the operational candidates.

Local selection took **63.107009 seconds**, including CV, serious validation fits, metrics and result serialization before rejection. No OpenAQ or Earth Engine extraction requests occurred in this phase. Raw caches and Phase 2C artifacts were preserved.

## Vertex preflight and exact blocker

A read-only ADC probe in project **airshedos**, region **us-central1**, passed the Vertex CustomJobs list API (**HTTP 200**). GCS bucket listing succeeded (**HTTP 200**) and returned **zero buckets**. `AIRSHEDOS_ML_BUCKET` is unset. Artifact Registry listing returned **HTTP 403, SERVICE_DISABLED**. Credentials and access tokens were not printed or stored in evidence. Existing ADC was reused; no credentials or IAM grants were created.

**No Vertex job was submitted because the scientific selection prerequisite failed.** Job ID/status, machine, container digest, GCS model URI and local/cloud parity are **not applicable / not performed**, not simulated successes. No endpoint, registry model, bucket, image repository or billable training infrastructure was created. Current official [custom-container guidance](https://cloud.google.com/vertex-ai/docs/training/create-custom-container), [prebuilt support](https://cloud.google.com/vertex-ai/docs/training/pre-built-containers) and [compute configuration](https://cloud.google.com/vertex-ai/docs/training/configure-compute) were inspected. A pinned CPU custom image would avoid assuming an old sklearn image supports these library versions; none was built without an eligible model.

If a separately authorized future experiment qualifies, its one-time cloud prerequisites are: choose a region; configure a dedicated `AIRSHEDOS_ML_BUCKET`; enable `artifactregistry.googleapis.com`; create a narrowly scoped Docker repository in the existing project; grant the training identity only necessary staging-read/output-write access and image-pull permissions; set `VERTEX_TRAINING_LOCATION`, `VERTEX_TRAIN_MACHINE_TYPE` (a small CPU machine such as n1-standard-4) and a digest-pinned training image. Then package only frozen train/validation inputs and manifests, never the locked test data, submit one genuine CustomJob, and compare validation metrics/counts/features/parameters. These setup actions were not authorized implicitly by an existing repository infrastructure workflow and were not performed during this no-go run.

## Regression verification

- **388 backend tests passed**, two existing dependency deprecation warnings, **21.22 s**. This includes 20 deterministic model tests and all 368 earlier tests.
- **26 browser tests passed**, **29.0 s**.
- Ruff lint and formatting passed for **70 Python files**; frontend lint, typecheck and production build passed.
- OpenAPI export and generated frontend types remain identical.
- Docker build/start/health passed for API and web with loopback bindings and existing read-only ADC configuration.
- Source, compiled frontend and model-run artifact secret scan: **1,751 files, zero findings**. Generated Parquets/model artifacts remain ignored.
- Git diff whitespace check passed. Final-head GitHub checks are tracked on the Phase 2D draft PR and must be green before merge.

CI installs separate pinned model dependencies and uses synthetic tests only; it never reads local real artifacts or submits a Vertex job. Cloud job/configuration tests and parity are not claimed: the explicit scientific no-go stopped that downstream implementation. No later stage is marked passed by substitute fixture evidence.

## Interpretation and verdict

**MODEL_NOT_ACCEPTED.** Do not proceed to Phase 2E from these results. The next scientific review should focus on the stale-input and seasonal-shift limitations, not widening the search until a favorable result appears. A new protocol requires an explicit decision; preserve the untouched final test set.

AirNow supplies 76.41% of the operational dataset. CPCB complete origins occur at local hours 14–18, while AirNow spans 24 hours; pooled scores cannot establish round-the-clock NCR performance. October and the known baseline test results show strong distribution shift. Adjacent six-hour targets overlap and are not independent samples. The provisional 72-hour buffer does not establish historical publication timing or revision freedom. No source attribution, medical prediction, prospective skill, spatial generalization, calibrated event probabilities or production readiness is claimed. Product runtime, forecast UI and API are unchanged. Stop after Phase 2D.
