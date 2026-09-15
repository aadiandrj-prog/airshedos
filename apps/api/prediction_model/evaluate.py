"""Single-use test gate and separate validation-only scientific diagnostics."""

import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from prediction.common import DatasetError, write_json
from prediction.frame import apply_spike_rule, freeze_spike_rule
from prediction_model.data import TARGET, read_json, sha, verify_dataset, verify_inputs
from prediction_model.estimators import fit, predict
from prediction_model.metrics import evaluate, qualifies
from prediction_model.train import save_predictions


def frozen_decision(output):
    output = Path(output)
    verify_inputs(output)
    for name, expected in read_json(output / "freeze_hashes.json").items():
        if sha(output / name) != expected:
            raise DatasetError("Frozen model artifact changed: " + name)
    decision = read_json(output / "model_selection_decision.json")
    if decision["status"] != "FROZEN_FOR_SINGLE_TEST":
        raise DatasetError("No eligible frozen candidate")
    return decision


def reserve_test(dataset, output, decision):
    path = Path(dataset) / "phase2d_test_access.json"
    record = {
        "reserved_at": datetime.now(UTC).isoformat(),
        "status": "reserved_before_read",
        "decision_sha256": sha(Path(output) / "model_selection_decision.json"),
        "model_sha256": decision["model_sha256"],
        "candidate_test_evaluations": 1,
        "reason": "Final frozen model only; failures require explicit audit, not automatic retry",
    }
    try:
        with path.open("x") as stream:
            json.dump(record, stream, indent=2)
    except FileExistsError:
        raise DatasetError("Test access already reserved; repeated evaluation forbidden") from None
    write_json(Path(output) / "test_access_audit.json", record)
    return record


def final_test(dataset, output):
    output = Path(output)
    decision = frozen_decision(output)
    manifest = verify_dataset(dataset)
    frozen_manifest = read_json(output / "dataset_manifest.json")
    if manifest["contract_sha256"] != frozen_manifest["contract_sha256"]:
        raise DatasetError("Test dataset differs from frozen source")
    audit = reserve_test(dataset, output, decision)
    # This is the only primary candidate evaluation path that can load test rows.
    rows = pd.read_parquet(
        Path(dataset) / "prediction_frame.parquet", filters=[("split", "==", "test")]
    )
    rows = rows[rows.operational_eligible].reset_index(drop=True)
    if rows.empty or not rows.split.eq("test").all():
        raise DatasetError("Invalid locked test population")
    model = joblib.load(output / "model.joblib")
    pred, clipped = predict(model, rows)
    metrics = evaluate(rows, pred, decision["thresholds"])
    metrics["negative_predictions_clipped"] = clipped
    baselines = {
        name: evaluate(rows, rows[col].to_numpy(), decision["thresholds"])
        for name, col in [
            ("persistence", "pm25_latest_available"),
            ("recent_mean_6h", "pm25_rolling_mean_6h"),
        ]
    }
    # Keep the baseline chosen in October fixed, rather than switching after test.
    reference = decision["baseline_reference"]
    go = qualifies(
        metrics, baselines[reference], read_json(output / "experiment_policy.json")["selection"]
    )
    verdict = "MODEL_ACCEPTED_FOR_OFFLINE_INTEGRATION" if go["eligible"] else "MODEL_NOT_ACCEPTED"
    report = {
        "verdict": verdict,
        "metrics": metrics,
        "baselines": baselines,
        "reference": reference,
        "predeclared_gates": go,
        "candidate_modified_after_test": False,
    }
    save_predictions(output / "test_predictions.parquet", rows, pred)
    write_json(output / "test_metrics.json", report)
    audit.update(
        status="completed",
        completed_at=datetime.now(UTC).isoformat(),
        rows=len(rows),
        metrics_sha256=sha(output / "test_metrics.json"),
    )
    write_json(output / "test_access_audit.json", audit)
    write_json(Path(dataset) / "phase2d_test_access.json", audit)
    return report


def diagnostics(dataset, output):
    """No additional test evaluation, including holdout and research ablations."""
    output = Path(output)
    decision = frozen_decision(output)
    if (output / "diagnostics.json").exists():
        raise DatasetError("Diagnostics already recorded")
    selected = decision["selected"]
    train, validation = (pd.read_parquet(output / f"{s}.parquet") for s in ("train", "validation"))
    policy = read_json(output / "experiment_policy.json")
    held = policy["holdout"]["station_id"]
    fitting = train[train.station_id != held].copy()
    scoring = validation[validation.station_id == held].copy()
    # Re-freeze spike choice from remaining training stations only for this separate stress test.
    rule = freeze_spike_rule(fitting)
    model = fit(fitting, selected["features"], selected["config"], policy["seed"])
    pred, clipped = predict(model, scoring)
    thresholds = fitting[TARGET].quantile(policy["slice_quantiles"]).tolist()
    metric = evaluate(scoring, pred, thresholds)
    # Metrics helper uses the PRIMARY fixed p85/30 rule. Report separately refrozen holdout rule.
    from prediction.evaluation import classification

    scoring = apply_spike_rule(scoring, rule)
    if rule.get("selected"):
        r = rule["selected"]
        valid = scoring.spike_next_6h.notna()
        spike = (
            (pred >= scoring[f"trailing_30d_p{r['percentile']}_pm25"].to_numpy())
            & (pred >= scoring.pm25_latest_available.to_numpy() * (1 + r["relative_increase"]))
            & (pred > scoring.pm25_latest_available.to_numpy())
        )
        metric["derived_spike"] = classification(scoring.loc[valid, "spike_next_6h"], spike[valid])
    else:
        metric["derived_spike"] = {"status": "unavailable_training_rule"}
    metric["negative_predictions_clipped"] = clipped
    holdout = {
        "label": "SPATIAL GENERALIZATION STRESS TEST",
        "held_out_station": held,
        "fit_rows": len(fitting),
        "score_rows": len(scoring),
        "split": "October validation only",
        "refrozen_spike_rule": rule,
        "metrics": metric,
        "baseline": evaluate(scoring, scoring.pm25_rolling_mean_6h.to_numpy(), thresholds),
        "primary_selection_unchanged": True,
    }
    research_path = Path(dataset) / "research_enriched_v1"
    rm = verify_dataset(research_path, operational=False)
    research = pd.read_parquet(
        research_path / "prediction_frame.parquet",
        filters=[("split", "in", ["train", "validation"])],
    )
    keys = ["station_id", "timestamp"]

    def align(rows):
        aligned = rows[keys].merge(research, on=keys, how="left", validate="one_to_one")
        if len(aligned) != len(rows) or not np.allclose(aligned[TARGET], rows[TARGET]):
            raise DatasetError("Research ablation targets/row keys differ")
        return aligned

    rt, rv = align(train), align(validation)
    research_model = fit(rt, rm["features"], selected["config"], policy["seed"])
    research_pred, research_clips = predict(research_model, rv)
    research_metrics = evaluate(validation, research_pred, decision["thresholds"])
    research_metrics["negative_predictions_clipped"] = research_clips
    ablation = {
        "label": "NOT DEPLOYMENT-SAFE AS CURRENTLY SOURCED",
        "deployment_safe": False,
        "fit_rows": len(rt),
        "score_rows": len(rv),
        "features": rm["features"],
        "source_hashes": rm["artifact_sha256"],
        "metrics": research_metrics,
        "interpretation": "Joint unbuffered AQ/weather intervention; weather effect not isolated",
        "same_operational_row_keys": True,
        "test_access": 0,
    }
    original = joblib.load(output / "model.joblib")
    base_pred, _ = predict(original, validation)
    base = evaluate(validation, base_pred, decision["thresholds"])["macro_station_mae"]
    rng = np.random.default_rng(policy["seed"])
    importance = []
    for feature in selected["features"]:
        changes = []
        for _ in range(3):
            perturbed = validation.copy()
            perturbed[feature] = rng.permutation(perturbed[feature].to_numpy())
            pred, _ = predict(original, perturbed)
            changes.append(
                evaluate(validation, pred, decision["thresholds"])["macro_station_mae"] - base
            )
        importance.append(
            {
                "feature": feature,
                "mean_macro_mae_increase": float(np.mean(changes)),
                "std": float(np.std(changes)),
            }
        )
    write_json(
        output / "feature_importance.json",
        {
            "method": "October permutation, 3 repeats, fixed seed; macro-station MAE increase",
            "interpretation": "Associational; correlation and permutations limit interpretation",
            "features": sorted(importance, key=lambda x: -x["mean_macro_mae_increase"]),
        },
    )
    report = {"holdout": holdout, "research_ablation": ablation, "test_access": 0}
    write_json(output / "diagnostics.json", report)
    return report
