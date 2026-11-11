# Offline predictive model selection (Phase 2D)

**Result: MODEL_NOT_ACCEPTED.** No predeclared candidate passed October's baseline gates. The November–December test period remains untouched by candidate evaluation. See [the verification report](PHASE_2D_VERIFICATION.md), [frozen decision summary](evidence/phase2d_decision.json) and [all candidate metrics](evidence/phase2d_validation_metrics.json). No prediction endpoint, forecast UI or Vertex endpoint was added.

## Task and availability

Experiment `prediction_model_v1` uses verified `prediction_dataset_v2`, OPERATIONAL_V1, with target `future_max_pm25_6h`: the same-station maximum over t+1…t+6, in µg/m³. All six target observations must exist. Inputs are buffered to t−72h or earlier, so the predicted outcomes are 73–78 hours after the newest input measurement. The target is never imputed or shifted backward.

The 72-hour buffer remains provisional. Observation time does not establish publication time, and historical revision availability remains unknown. The correct description is **offline operational-profile model under a provisional availability contract**, not prospective or real-time readiness. No probability calibration, medical-risk inference, causal source attribution or regulatory spike definition is established.

## Reproducible bounded protocol

The versioned policy is [configs/prediction_model_v1.json](../configs/prediction_model_v1.json). It was committed before the first real fit. Dependencies are separate from product runtime in `apps/api/requirements-model.lock`: scikit-learn 1.9.1, XGBoost 3.4.1, NumPy 2.3.5, pandas 2.3.3, SciPy 1.18.1, joblib 1.6.0 and supporting pinned packages. CPU-only fitting uses one thread and seed 42. No model is fitted by FastAPI or the browser.

1. Validate Phase 2C source SHA-256 hashes and the feature-availability contract. Read only train/validation rows through Parquet filters, then persist separate immutable input snapshots and hashes. Integrity hashing of original bytes is distinct from loading test records for evaluation.
2. Within training, use expanding folds: February 19→June 1 scored June; February 19→July 1 scored July; February 19→August 1 scored August–September. Purge fitting target windows at each boundary and score windows at their ending boundary. All dates are 2025, UTC, end exclusive. No random splits or early stopping.
3. Search two parameter choices and raw/log1p targets within each family/subset/weighting policy. Three families × two subsets × two weighting policies × four parameter/transform choices = 48 configurations, 144 CV fits. Mean fold macro-station MAE selects one configuration per policy, yielding 12 serious October candidates.
4. Select using October macro-station MAE first, pooled MAE second, then simpler model within 0.25 µg/m³ practical equivalence. No test metric is supplied to selection. Fit only on the original training period; no October refit.
5. Freeze a machine-readable decision before any final test access. If no candidate passes, record NO_MODEL_ACCEPTED and stop. That is the branch taken here.

Ridge evaluates α 10/100, training-only median imputation with explicit missingness indicators (all-empty columns retained), standardization and SVD regression. For station-balanced fits, scaling and regression receive weights; medians remain unweighted training medians. Histogram gradient boosting evaluates 7/15 leaves, 150 iterations, learning rate .05, minimum leaf samples 30 and L2 10, with early stopping explicitly disabled. XGBoost evaluates depths 2/4, 150 estimators, learning rate .05, minimum child weight 10, L2 10, row/column subsampling .8, CPU histogram method. Trees route missing optional values natively. These behaviors follow the [scikit-learn estimator documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html) and [XGBoost Python API](https://xgboost.readthedocs.io/en/stable/python/python_api.html).

All preprocessing is fitted anew inside each training fold. No target encoding, station ID feature, learned imputation from validation, target imputation, target winsorization or positive prediction cap. After any inverse log1p transformation, predictions are clipped only at zero; nonfinite outputs fail rather than being hidden. Clipping counts are included in metrics.

## Features and station weights

**CORE_PM (19 features):** PM2.5 latest available; lags 73/74/75/78/84/96h; means 3/6/12h and std 6h ending at t−72; 30-day history count and p85/p90/p95; station-local hour, weekday, month and weekend. Missing percentiles are allowed and handled by the fitted model. Required PM core input availability defines the unchanged Phase 2C operational population.

**OPERATIONAL_EXTENDED (29 features):** CORE_PM plus CO/NO2/O3/PM10/SO2 at lags 72/73h. Units remain in feature names: CO/NO2/SO2 ppb, O3/PM10 µg/m³. No rows are deleted for missing optional inputs. All candidates share the same evaluation population. Both subsets exclude ERA5 and station identity.

Both unweighted and station-balanced fitting are evaluated. Within the fitting subset only, each row receives `N / (number_of_stations × station_row_count)`, giving equal aggregate weight per station and mean weight one. CV weights never use fold-score, October or test counts. No weight tuning follows validation results.

## Metrics and acceptance

Macro-station MAE is the unweighted mean of each eligible station's MAE. Also report pooled MAE/RMSE, macro-station RMSE, signed bias (prediction−actual), underprediction rate, station/hour/month/target-band slices and sample counts. Training-derived p50/p90/p99 target thresholds are 49/112.3/198 µg/m³. The high-pollution slice uses target > training p90. CV learns equivalent thresholds from each fold's fitting subset only.

The baseline reference is whichever of persistence and recent six-hour mean has lower October macro-station MAE on identical rows. Both were reproduced from Phase 2C artifacts. The fixed go/no-go policy requires all of:

- At least 2% macro-station MAE improvement over the reference.
- Pooled MAE no more than 2% worse.
- At least 60% of stations improve.
- No station MAE above reference MAE ×1.25+2 µg/m³.

If a candidate qualifies, the same gates are predeclared for interpreting the single final test. Rejection never permits retuning on that test. Known Phase 2C naive test figures are not used to choose candidate configurations. The strongest rejected October candidate had macro MAE 61.929456 versus baseline 53.926835, and pooled MAE 60.473177 versus 47.546265. All candidates failed; no model family was promoted.

Derived spike metrics compare each regression prediction with the same origin-available p85, 30% relative increase and strictly positive worsening components from Phase 2C. Missing reference/label rows are excluded only from classification metrics. No new threshold or separate classifier is fitted, and no event probabilities are emitted. Precision/recall/F1 and confusion counts are secondary, never the selection objective.

## Freeze, artifacts and test protection

Real artifacts remain ignored under `data/models/phase2d_v1/`: source/availability manifests, input hashes, separate training/validation Parquets, experiment policy, CV results, validation baselines/candidates, training thresholds, rejection decision and test-access audit. Committed evidence contains only aggregate metrics, configuration and provenance. No binary model or source dataset is committed.

A successful selection branch would additionally save a model bundle, feature order, dependency versions, model/input manifests, validation predictions and model checksum. Its evaluator verifies frozen hashes and atomically reserves one dataset-level test access before reading test rows. Repeated evaluation—even into another output folder—fails; a failed reserved test requires explicit audit rather than silent retry. A rejected decision fails before any test artifact read. Input schema ordering, serialization, preprocessing, weights, metrics and rejection behavior have deterministic synthetic tests.

No selected-model `model_input_contract.json` was emitted in this run because there is no selected model or feature policy to bind. The implemented accepted-branch contract specifies required/optional columns and ordering, units, NaN behavior, UTC interval-end semantics, provisional 72-hour buffer, schema version, target horizon and nonnegative postprocessing. It cannot label a research profile deployment-safe.

## Conditional diagnostics and Vertex boundary

The brief places station-8118 holdout, research ablation, finalist seed checks, feature importance and Vertex after model selection. They were **not executed** after the no-go. A future qualifying run would use the frozen family/config, fit holdout preprocessing on the other stations only, refreeze holdout spike statistics on those fitting stations, and report the intentionally difficult AirNow holdout separately. The prepared diagnostic path scores October only and never opens another test evaluation. Research aligns exactly the operational train/validation row keys and replaces inputs with retrospective AQ/weather; that joint intervention cannot isolate meteorology's contribution and remains non-deployable. Validation permutation importance would be associational and limited by correlated features, not causal evidence.

The read-only live cloud probe found ADC/Vertex access working in project `airshedos`, `us-central1`. There are no GCS buckets; the ML bucket setting is absent; Artifact Registry is disabled. The scientific gate is the primary blocker. No training image, CustomJob, model registration or endpoint was created. Local/Vertex parity was not performed. See the verification report for exact setup requirements if a later, separately authorized experiment qualifies. Current [custom-container](https://cloud.google.com/vertex-ai/docs/training/create-custom-container) and [prebuilt-container](https://cloud.google.com/vertex-ai/docs/training/pre-built-containers) documentation was inspected; an old sklearn image is not assumed available or dependency-compatible.

## Local commands

```sh
uv pip install --python apps/api/.venv/bin/python -r apps/api/requirements-model.lock
OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 apps/api/.venv/bin/python apps/api/scripts/train_prediction_models.py \
  --dataset data/processed/live_acceptance/full_dataset \
  --output data/models/phase2d_v1 \
  --policy configs/prediction_model_v1.json
```

The recorded experiment directory refuses overwrite, and a frozen decision refuses reselection. Do not launch another search to circumvent the rejection. `evaluate_prediction_model.py final-test` is exclusively for a qualifying frozen decision and is blocked for this experiment. CI uses synthetic inputs and has no live cloud training path. Model dependencies are not added to the runtime API requirements or image.

The result does not justify Phase 2E. AirNow dominance, afternoon-only CPCB eligibility, seasonal shift, stale inputs, uncertain revisions and overlapping targets must remain visible in any future protocol review. No live product behavior changed.
