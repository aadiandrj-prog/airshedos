"""Hash validation without exposing the locked test population to selection."""

import hashlib
import json
from pathlib import Path

import pandas as pd

from prediction.availability import OPERATIONAL_V1, validate_availability_manifest
from prediction.common import DatasetError, digest, write_json
from prediction.frame import FrameConfig

TARGET = "future_max_pm25_6h"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def verify_dataset(path, operational=True):
    path = Path(path)
    m = read_json(path / "dataset_manifest.json")
    if m["synthetic"] or m["version"] != "prediction_dataset_v2":
        raise DatasetError("Real verified Phase 2C artifacts required")
    for name in (
        "prediction_frame.parquet",
        "normalized_aq.parquet",
        "normalized_era5.parquet",
        "feature_availability_manifest.json",
    ):
        if sha(path / name) != m["artifact_sha256"].get(name):
            raise DatasetError("Dataset artifact hash mismatch")
    contract = digest(
        {
            k: m[k]
            for k in ("config", "stations", "features", "targets", "artifact_sha256", "synthetic")
        }
    )
    if contract != m["contract_sha256"]:
        raise DatasetError("Dataset contract hash mismatch")
    validate_availability_manifest(
        read_json(path / "feature_availability_manifest.json"),
        m["features"],
        FrameConfig(**m["config"]),
    )
    if operational and (
        m["profile"] != OPERATIONAL_V1 or m["config"]["aq_availability_buffer_hours"] != 72
    ):
        raise DatasetError("Primary model requires the verified 72-hour operational contract")
    return m


def read_selection_rows(path):
    # Hashing bytes for integrity is not a candidate-model test evaluation.
    # Parquet filters return only train/validation; do not deserialize a full frame then slice.
    frame = pd.read_parquet(
        Path(path) / "prediction_frame.parquet", filters=[("split", "in", ["train", "validation"])]
    )
    if not frame.split.isin(["train", "validation"]).all():
        raise DatasetError("Test or purged rows entered selection")
    return frame[frame.operational_eligible].reset_index(drop=True)


def assert_selection(frame):
    if frame.empty or not frame.split.isin(["train", "validation"]).all():
        raise DatasetError("Selection accepts train/validation only")
    if frame.timestamp.max() >= pd.Timestamp("2025-11-01T00:00Z"):
        raise DatasetError("Locked test period entered selection")


def training_folds(train, policy):
    if not train.split.eq("train").all():
        raise DatasetError("Cross-validation accepts TRAIN only")
    result = []
    for fold in policy["folds"]:
        start, boundary, end = (
            pd.Timestamp(fold[k]) for k in ("fit_start", "fit_end", "score_end")
        )
        if end > pd.Timestamp("2025-10-01T00:00Z") or not start < boundary < end:
            raise DatasetError("CV fold exceeds training period")
        fit = train[(train.timestamp >= start) & (train.target_window_end < boundary)]
        score = train[(train.timestamp >= boundary) & (train.target_window_end < end)]
        if fit.empty or score.empty or not fit.target_window_end.max() < score.timestamp.min():
            raise DatasetError("Empty or overlapping fold")
        result.append((fit.copy(), score.copy()))
    return result


def subset_features(features, subset):
    if subset == "OPERATIONAL_EXTENDED":
        result = features.copy()
    elif subset == "CORE_PM":
        result = [
            f
            for f in features
            if f.startswith(("pm25_", "trailing_30d_"))
            or f in {"history_count_30d", "hour_of_day", "day_of_week", "month", "weekend"}
        ]
    else:
        raise DatasetError("Unknown operational subset")
    if any(
        f.startswith(("future_", "era5_")) or f in {"station_id", "spike_next_6h"} for f in result
    ):
        raise DatasetError("Unsafe primary model feature")
    return result


def matrix(frame, features):
    if len(features) != len(set(features)) or any(f not in frame for f in features):
        raise DatasetError("Model feature schema mismatch")
    return frame.loc[:, features].astype(float)


def prepare(dataset, output, policy_path):
    output = Path(output)
    if (Path(dataset) / "phase2d_test_access.json").exists():
        raise DatasetError("Dataset test already accessed; new selection is forbidden")
    if output.exists() and any(output.iterdir()):
        raise DatasetError("Use a new output directory; never overwrite a model experiment")
    manifest = verify_dataset(dataset)
    rows = read_selection_rows(dataset)
    assert_selection(rows)
    policy = read_json(policy_path)
    if policy["profile"] != manifest["profile"]:
        raise DatasetError("Policy profile mismatch")
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "experiment_policy.json", policy)
    write_json(output / "dataset_manifest.json", manifest)
    write_json(
        output / "feature_availability_manifest.json",
        read_json(Path(dataset) / "feature_availability_manifest.json"),
    )
    # Existing baseline artifact is preserved but only train/validation metrics exposed to tuner.
    baseline = read_json(Path(dataset) / "baseline_metrics.json")
    write_json(
        output / "phase2c_selection_baselines.json",
        {k: baseline["splits"][k] for k in ("train", "validation")},
    )
    for split in ("train", "validation"):
        rows[rows.split == split].to_parquet(output / f"{split}.parquet", index=False)
    write_json(
        output / "input_hashes.json", {f.name: sha(f) for f in output.iterdir() if f.is_file()}
    )
    write_json(
        output / "test_access_audit.json",
        {
            "selection_test_rows": 0,
            "candidate_test_evaluations": 0,
            "hash_only_integrity_check": True,
            "policy": "single atomic reservation before test read; no automatic retry",
        },
    )
    return manifest


def verify_inputs(output):
    output = Path(output)
    for name, expected in read_json(output / "input_hashes.json").items():
        if sha(output / name) != expected:
            raise DatasetError("Frozen experiment input was modified: " + name)
