"""Predeclared CV, October selection and immutable pre-test decision."""

import itertools
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from prediction.availability import OPERATIONAL_V1
from prediction.common import DatasetError, digest, write_json
from prediction_model.data import (
    TARGET,
    assert_selection,
    read_json,
    sha,
    subset_features,
    training_folds,
    verify_inputs,
)
from prediction_model.estimators import fit, predict, versions
from prediction_model.metrics import evaluate, qualifies


def git_commit():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def input_contract(features, manifest, family):
    if manifest["profile"] != OPERATIONAL_V1 or any(f.startswith("era5_") for f in features):
        raise DatasetError("Research profile cannot become the operational model contract")
    required = [
        f
        for f in features
        if f.startswith("pm25_")
        or f in {"hour_of_day", "day_of_week", "month", "weekend", "history_count_30d"}
    ]

    def unit(f):
        if f.endswith("_ppb") or "_ppb_" in f:
            return "ppb"
        if "_ppm_" in f:
            return "ppm"
        if f.startswith(("pm25_", "trailing_30d_")) or "_ug_m3_" in f:
            return "µg/m³"
        return "hours" if f == "history_count_30d" else "calendar integer"

    return {
        "schema_version": "airshedos_model_input_v1",
        "profile": OPERATIONAL_V1,
        "deployment_safe": False,
        "deployment_condition": (
            "offline operational-profile model under a provisional availability contract"
        ),
        "feature_order": features,
        "required_features": required,
        "optional_features": [f for f in features if f not in required],
        "units": {f: unit(f) for f in features},
        "aq_availability_buffer_hours": 72,
        "timestamps": "UTC source interval end; inputs <= origin-72h; no forward-fill",
        "missing_values": "PM core/calendar required; optional/history percentiles may be NaN; "
        + (
            "training-only median imputation with indicators"
            if family == "ridge"
            else "native tree NaN routing"
        ),
        "target": TARGET,
        "unit": "µg/m³",
        "target_hours": [1, 2, 3, 4, 5, 6],
        "postprocessing": "max(0, prediction); no upper cap",
        "probabilities": False,
        "station_identity_feature": False,
    }


def save_predictions(path, rows, predictions):
    result = rows[["station_id", "timestamp", "split", TARGET]].copy()
    result["prediction"] = predictions
    result.to_parquet(path, index=False)


def selection(output):
    output = Path(output)
    if (output / "model_selection_decision.json").exists():
        raise DatasetError("Selection is frozen; cannot retune this experiment")
    verify_inputs(output)
    policy = read_json(output / "experiment_policy.json")
    manifest = read_json(output / "dataset_manifest.json")
    train, validation = (
        pd.read_parquet(output / f"{split}.parquet") for split in ("train", "validation")
    )
    assert_selection(pd.concat([train, validation]))
    if not train.split.eq("train").all() or not validation.split.eq("validation").all():
        raise DatasetError("Split isolation violated")
    started = time.monotonic()
    thresholds = train[TARGET].quantile(policy["slice_quantiles"]).tolist()
    write_json(
        output / "training_thresholds.json",
        {"source": "training targets only", "thresholds": thresholds},
    )
    folds = training_folds(train, policy)
    fold_counts = [
        {
            "fit_n": len(a),
            "score_n": len(b),
            "max_fit_target_end": a.target_window_end.max().isoformat(),
            "min_score_origin": b.timestamp.min().isoformat(),
        }
        for a, b in folds
    ]
    baseline = {
        name: evaluate(validation, validation[col].to_numpy(), thresholds)
        for name, col in [
            ("persistence", "pm25_latest_available"),
            ("recent_mean_6h", "pm25_rolling_mean_6h"),
        ]
    }
    recorded = read_json(output / "phase2c_selection_baselines.json")["validation"]["pooled"]
    for name, metrics in baseline.items():
        for key in ("n", "mae", "rmse"):
            if not np.isclose(metrics["pooled"][key], recorded[name][key], rtol=1e-10):
                raise DatasetError("Phase 2C baseline reproduction differs")
    reference = min(baseline, key=lambda name: baseline[name]["macro_station_mae"])
    write_json(output / "validation_baselines.json", {"reference": reference, "metrics": baseline})
    cv, serious, bundles = [], [], {}
    for family, subset, weighting in itertools.product(
        policy["families"], policy["feature_subsets"], policy["weighting"]
    ):
        features = subset_features(manifest["features"], subset)
        group = []
        for transform, params in itertools.product(
            policy["target_transforms"], policy["families"][family]
        ):
            config = {
                "family": family,
                "subset": subset,
                "weighting": weighting,
                "transform": transform,
                "parameters": params,
            }
            scores = []
            for fit_rows, score_rows in folds:
                model = fit(fit_rows, features, config, policy["seed"])
                prediction, clipped = predict(model, score_rows)
                # Each fold's target-band thresholds are learned on that fold's fitting rows.
                t = fit_rows[TARGET].quantile(policy["slice_quantiles"]).tolist()
                metric = evaluate(score_rows, prediction, t)
                scores.append(
                    {
                        "macro_station_mae": metric["macro_station_mae"],
                        "pooled": metric["pooled"],
                        "clipped": clipped,
                    }
                )
            record = {
                "id": digest(config)[:12],
                "config": config,
                "features": features,
                "folds": scores,
                "cv_macro_station_mae": float(np.mean([s["macro_station_mae"] for s in scores])),
            }
            group.append(record)
            cv.append(record)
        chosen = min(group, key=lambda r: (r["cv_macro_station_mae"], r["id"]))
        model = fit(train, features, chosen["config"], policy["seed"])
        prediction, clipped = predict(model, validation)
        metric = evaluate(validation, prediction, thresholds)
        metric["negative_predictions_clipped"] = clipped
        chosen = {
            **chosen,
            "validation": metric,
            "go_no_go": qualifies(metric, baseline[reference], policy["selection"]),
        }
        serious.append(chosen)
        bundles[chosen["id"]] = model
        print(
            f"validated {family} {subset} {weighting}: macro_MAE={metric['macro_station_mae']:.4f}",
            flush=True,
        )
        write_json(output / "cv_results.json", {"fold_counts": fold_counts, "candidates": cv})
        write_json(output / "validation_candidates.json", serious)
    eligible = [r for r in serious if r["go_no_go"]["eligible"]]
    decision = {
        "timestamp": datetime.now(UTC).isoformat(),
        "git_commit": git_commit(),
        "experiment_policy_sha256": sha(output / "experiment_policy.json"),
        "input_hashes_sha256": sha(output / "input_hashes.json"),
        "feature_profile": OPERATIONAL_V1,
        "baseline_reference": reference,
        "baseline": baseline[reference],
        "random_seed_policy": policy["stability_seeds"],
        "fixed_primary_seed": policy["seed"],
        "thresholds": thresholds,
        "test_access_before_freeze": 0,
        "local_selection_seconds": time.monotonic() - started,
    }
    if not eligible:
        decision.update(
            status="NO_MODEL_ACCEPTED", reason="No candidate passed predeclared October gates"
        )
        write_json(output / "model_selection_decision.json", decision)
        return decision
    margin = policy["selection"]["practical_equivalence_absolute"]
    best = min(r["validation"]["macro_station_mae"] for r in eligible)
    tied = [r for r in eligible if r["validation"]["macro_station_mae"] <= best + margin]
    pooled_best = min(r["validation"]["pooled"]["mae"] for r in tied)
    tied = [r for r in tied if r["validation"]["pooled"]["mae"] <= pooled_best + margin]
    rank = {"ridge": 0, "hist_gradient_boosting": 1, "xgboost": 2}
    winner = min(tied, key=lambda r: (rank[r["config"]["family"]], len(r["features"]), r["id"]))
    model = bundles[winner["id"]]
    stability = []
    trees = [r for r in serious if r["config"]["family"] != "ridge"]
    tree = min(trees, key=lambda r: r["validation"]["macro_station_mae"])
    for seed in policy["stability_seeds"]:
        repeat = fit(train, tree["features"], tree["config"], seed)
        pred, _ = predict(repeat, validation)
        metric = evaluate(validation, pred, thresholds)
        stability.append(
            {
                "candidate_id": tree["id"],
                "seed": seed,
                "macro_station_mae": metric["macro_station_mae"],
                "pooled": metric["pooled"],
            }
        )
    write_json(output / "seed_stability.json", stability)
    joblib.dump(model, output / "model.joblib")
    pred, _ = predict(model, validation)
    save_predictions(output / "validation_predictions.parquet", validation, pred)
    contract = input_contract(winner["features"], manifest, winner["config"]["family"])
    write_json(output / "model_input_contract.json", contract)
    write_json(
        output / "feature_schema.json",
        {"features": winner["features"], "dtypes": "numeric float; NaN allowed per input contract"},
    )
    write_json(output / "environment.json", versions())
    decision.update(
        status="FROZEN_FOR_SINGLE_TEST",
        selected=winner,
        model_sha256=sha(output / "model.joblib"),
        reason="Passed October gates; macro MAE, pooled MAE, simplicity within 0.25 µg/m³",
        local_selection_seconds=time.monotonic() - started,
    )
    write_json(output / "model_selection_decision.json", decision)
    frozen = {
        name: sha(output / name)
        for name in (
            "model_selection_decision.json",
            "model.joblib",
            "feature_schema.json",
            "model_input_contract.json",
            "experiment_policy.json",
            "input_hashes.json",
            "training_thresholds.json",
            "environment.json",
        )
    }
    write_json(output / "freeze_hashes.json", frozen)
    train_pred, clipped = predict(model, train)
    metrics = evaluate(train, train_pred, thresholds)
    metrics["negative_predictions_clipped"] = clipped
    write_json(output / "training_metrics.json", metrics)
    write_json(
        output / "model_manifest.json",
        {
            "model_version": policy["version"],
            "dataset_version": manifest["version"],
            "profile": OPERATIONAL_V1,
            "feature_order": winner["features"],
            "target": TARGET,
            "aq_availability_buffer_hours": 72,
            "config": winner["config"],
            "seed": policy["seed"],
            "git_commit": git_commit(),
            "library_versions": versions(),
            "source_artifact_hashes": manifest["artifact_sha256"],
            "dataset_contract_sha256": manifest["contract_sha256"],
            "split_boundaries": manifest["split_boundaries"],
            "stations": [s["id"] for s in manifest["stations"]],
            "training_rows": len(train),
            "validation_rows": len(validation),
            "selection_decision_sha256": sha(output / "model_selection_decision.json"),
            "availability": contract["deployment_condition"],
            "deployment_safe": False,
        },
    )
    return decision
