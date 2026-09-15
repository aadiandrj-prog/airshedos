"""Deterministic synthetic checks; never cloud jobs or the real locked test artifact."""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from prediction.availability import OPERATIONAL_V1, RESEARCH_ENRICHED_V1, availability_manifest
from prediction.common import DatasetError, digest, write_json
from prediction.frame import FrameConfig
from prediction_model.data import (
    TARGET,
    assert_selection,
    matrix,
    read_selection_rows,
    sha,
    subset_features,
    training_folds,
    verify_dataset,
    verify_inputs,
)
from prediction_model.estimators import fit, predict, weights
from prediction_model.evaluate import reserve_test
from prediction_model.metrics import evaluate, nonnegative, qualifies, regression, spike_prediction
from prediction_model.train import input_contract


@pytest.fixture
def rows():
    n = 120
    time = pd.date_range("2025-05-01T00:30Z", periods=n, freq="24h")
    y = np.arange(n, dtype=float) + 10
    return pd.DataFrame(
        {
            "station_id": ["a"] * 90 + ["b"] * 30,
            "timestamp": time,
            "target_window_end": time + pd.Timedelta(hours=6),
            "split": "train",
            TARGET: y,
            "pm25_latest_available": y - 2,
            "pm25_lag_73h": y - 3,
            "hour_of_day": 6,
            "trailing_30d_p85_pm25": 20.0,
            "spike_next_6h": y > 50,
        }
    )


def config(family="ridge"):
    params = {
        "ridge": {"alpha": 10},
        "hist_gradient_boosting": {"max_iter": 3},
        "xgboost": {"n_estimators": 3, "max_depth": 2},
    }
    return {
        "family": family,
        "parameters": params[family],
        "transform": "raw",
        "weighting": "unweighted",
    }


def test_station_weights_use_fitting_counts_only(rows):
    w = weights(rows, "station_balanced")
    assert w.mean() == pytest.approx(1)
    assert w[:90].sum() == pytest.approx(w[90:].sum())
    assert np.all(weights(rows, "unweighted") == 1)
    with pytest.raises(DatasetError):
        weights(rows.assign(split="validation"), "station_balanced")


def test_cv_purges_future_targets_and_never_accepts_validation(rows):
    p = {
        "folds": [
            {
                "fit_start": "2025-05-01T00:00Z",
                "fit_end": "2025-06-01T00:00Z",
                "score_end": "2025-07-01T00:00Z",
            }
        ]
    }
    fit_rows, score = training_folds(rows, p)[0]
    assert fit_rows.target_window_end.max() < score.timestamp.min()
    assert score.target_window_end.max() < pd.Timestamp(p["folds"][0]["score_end"])
    with pytest.raises(DatasetError):
        training_folds(rows.assign(split="validation"), p)
    p["folds"][0]["score_end"] = "2025-11-02T00:00Z"
    with pytest.raises(DatasetError):
        training_folds(rows, p)


def test_selection_rejects_test_and_mislabelled_test_timestamps(rows):
    with pytest.raises(DatasetError):
        assert_selection(rows.assign(split="test"))
    with pytest.raises(DatasetError):
        assert_selection(rows.assign(timestamp=pd.Timestamp("2025-11-01T00:00Z")))


def test_parquet_selection_excludes_test_before_return(tmp_path):
    pd.DataFrame(
        {
            "split": ["train", "validation", "test", "purged"],
            "operational_eligible": [True] * 4,
            TARGET: [1, 2, 99999, 99999],
        }
    ).to_parquet(tmp_path / "prediction_frame.parquet")
    selected = read_selection_rows(tmp_path)
    assert selected[TARGET].tolist() == [1, 2]


def test_training_only_imputation_scaling_and_no_target_imputation(rows):
    rows["optional"] = 1.0
    rows.loc[:10, "optional"] = np.nan
    bundle = fit(rows, ["pm25_latest_available", "optional"], config())
    imp = bundle["estimator"].named_steps["impute"]
    assert imp.statistics_[1] == 1
    before = bundle["estimator"].named_steps["scale"].mean_.copy()
    pred, _ = predict(bundle, rows.assign(optional=1e9, split="validation"))
    assert len(pred) == len(rows)
    np.testing.assert_array_equal(before, bundle["estimator"].named_steps["scale"].mean_)
    bad = rows.copy()
    bad.loc[0, TARGET] = np.nan
    with pytest.raises(DatasetError):
        fit(bad, ["pm25_latest_available"], config())
    with pytest.raises(DatasetError):
        fit(rows.assign(split="test"), ["pm25_latest_available"], config())


@pytest.mark.parametrize("family", ["ridge", "hist_gradient_boosting", "xgboost"])
@pytest.mark.parametrize("transform", ["raw", "log1p"])
def test_model_roundtrip_preserves_order_and_predictions(rows, tmp_path, family, transform):
    c = {**config(family), "transform": transform, "weighting": "station_balanced"}
    features = ["pm25_lag_73h", "pm25_latest_available"]
    model = fit(rows, features, c)
    before, _ = predict(model, rows)
    joblib.dump(model, tmp_path / "model.joblib")
    after, _ = predict(joblib.load(tmp_path / "model.joblib"), rows[rows.columns[::-1]])
    np.testing.assert_allclose(before, after)
    assert (after >= 0).all()
    assert model["features"] == features


def test_metrics_macro_weighting_high_bias_and_slices(rows):
    y = rows[TARGET].to_numpy()
    p = y + np.where(rows.station_id.eq("a"), 2, -10)
    result = evaluate(rows, p, [50, 100, 120])
    assert result["macro_station_mae"] == 6
    assert result["pooled"]["mae"] == 4
    assert result["pooled"]["bias"] == -1
    assert result["high_pollution"]["bias"] == -10
    assert result["high_pollution"]["underprediction_rate"] == 1
    assert sum(x["n"] for x in result["by_local_hour"].values()) == len(rows)
    assert regression([1, 3], [3, 1])["rmse"] == 2


def test_postprocessing_clips_negatives_without_positive_cap():
    p, count = nonnegative([-5, 0, 25000])
    assert p.tolist() == [0, 0, 25000] and count == 1
    with pytest.raises(DatasetError):
        nonnegative([np.inf])


def test_spike_uses_frozen_rule_and_excludes_missing_reference(rows):
    r = rows.iloc[:4].copy()
    r["pm25_latest_available"] = 10.0
    r["trailing_30d_p85_pm25"] = [12, 12, 12, np.nan]
    r["spike_next_6h"] = [True, False, True, None]
    report = spike_prediction(r, np.array([13, 12.99, 10, 100]))
    assert (report["tp"], report["tn"], report["fn"], report["fp"]) == (1, 1, 1, 0)
    assert report["n"] == 3 and report["unavailable_labels"] == 1


def test_schema_and_research_contract_rejection(rows):
    features = ["pm25_latest_available", "hour_of_day", "co_ppb_lag_72h"]
    assert subset_features(features, "CORE_PM") == features[:2]
    for bad in ["era5_temperature_2m", "future_max_pm25_6h", "station_id"]:
        with pytest.raises(DatasetError):
            subset_features(features + [bad], "OPERATIONAL_EXTENDED")
    with pytest.raises(DatasetError):
        matrix(rows, ["nonexistent"])
    contract = input_contract(features, {"profile": OPERATIONAL_V1}, "ridge")
    assert contract["units"]["co_ppb_lag_72h"] == "ppb"
    assert contract["deployment_safe"] is False and contract["aq_availability_buffer_hours"] == 72
    with pytest.raises(DatasetError):
        input_contract(features, {"profile": RESEARCH_ENRICHED_V1}, "ridge")


def test_one_test_reservation_across_different_output_directories(tmp_path):
    output = tmp_path / "experiment"
    output.mkdir()
    write_json(output / "model_selection_decision.json", {"selected": "frozen"})
    reserve_test(tmp_path, output, {"model_sha256": "abc"})
    other = tmp_path / "another"
    other.mkdir()
    write_json(other / "model_selection_decision.json", {"selected": "changed"})
    with pytest.raises(DatasetError, match="repeated evaluation"):
        reserve_test(tmp_path, other, {"model_sha256": "def"})
    assert (
        json.loads((tmp_path / "phase2d_test_access.json").read_text())[
            "candidate_test_evaluations"
        ]
        == 1
    )


def test_frozen_input_hashes_detect_tampering(tmp_path):
    f = tmp_path / "train.parquet"
    f.write_bytes(b"original")
    write_json(tmp_path / "input_hashes.json", {f.name: sha(f)})
    verify_inputs(tmp_path)
    f.write_bytes(b"changed")
    with pytest.raises(DatasetError):
        verify_inputs(tmp_path)


def test_dataset_hash_and_contract_verification(tmp_path):
    config_ = FrameConfig("2025-02-19T00:00Z", "2026-01-01T00:00Z")
    features = ["pm25_latest_available"]
    write_json(
        tmp_path / "feature_availability_manifest.json", availability_manifest(features, config_)
    )
    for name in ["prediction_frame.parquet", "normalized_aq.parquet", "normalized_era5.parquet"]:
        (tmp_path / name).write_bytes(b"test snapshot")
    m = {
        "version": "prediction_dataset_v2",
        "synthetic": False,
        "profile": OPERATIONAL_V1,
        "config": config_.to_dict(),
        "features": features,
        "stations": [],
        "targets": {},
        "artifact_sha256": {p.name: sha(p) for p in tmp_path.iterdir()},
    }
    m["contract_sha256"] = digest(
        {
            k: m[k]
            for k in ("config", "stations", "features", "targets", "artifact_sha256", "synthetic")
        }
    )
    write_json(tmp_path / "dataset_manifest.json", m)
    assert verify_dataset(tmp_path)["version"] == "prediction_dataset_v2"
    (tmp_path / "prediction_frame.parquet").write_bytes(b"modified")
    with pytest.raises(DatasetError):
        verify_dataset(tmp_path)


def test_go_gate_detects_low_volume_station_failure(rows):
    policy = json.loads(
        (Path(__file__).resolve().parents[3] / "configs/prediction_model_v1.json").read_text()
    )["selection"]
    baseline = evaluate(rows, rows[TARGET].to_numpy() + 10, [50, 100, 120])
    candidate = evaluate(
        rows, rows[TARGET].to_numpy() + np.where(rows.station_id.eq("a"), 0, 20), [50, 100, 120]
    )
    assert not qualifies(candidate, baseline, policy)["eligible"]
    perfect = evaluate(rows, rows[TARGET].to_numpy(), [50, 100, 120])
    assert qualifies(perfect, baseline, policy)["eligible"]
