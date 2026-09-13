import math

import numpy as np
import pandas as pd

from prediction.common import DatasetError
from prediction.frame import (
    TARGETS,
    apply_spike_rule,
    construct,
    freeze_spike_rule,
    split_boundaries,
)


def validate(frame, aq, weather, stations, config, features, frozen, require_operational=False):
    if any(
        c in TARGETS or c.startswith("future_") or c in {"split", "regression_eligible"}
        for c in features
    ):
        raise DatasetError("Target/split leakage into feature matrix")
    expected, allowed_features = construct(aq, weather, stations, config)
    if features != allowed_features:
        raise DatasetError("Feature manifest is not the explicit builder allowlist")
    if frozen != freeze_spike_rule(expected):
        raise DatasetError("Spike rule does not match training-only selection")
    expected = apply_spike_rule(expected, frozen)
    try:
        pd.testing.assert_frame_equal(
            frame.reset_index(drop=True),
            expected.reset_index(drop=True),
            check_dtype=False,
            check_exact=False,
            rtol=1e-12,
            atol=1e-12,
        )
    except AssertionError:
        raise DatasetError(
            "Frame differs from independently reconstructed lags, rolls, targets or splits"
        ) from None
    if frame.duplicated(["station_id", "timestamp"]).any():
        raise DatasetError("Duplicate station-hour")
    if not (frame.feature_observation_end <= frame.timestamp).all():
        raise DatasetError("Future observation entered features")
    if not (frame.target_window_start == frame.timestamp + pd.Timedelta(hours=1)).all():
        raise DatasetError("Target start is not t+1")
    if not (frame.target_window_end == frame.timestamp + pd.Timedelta(hours=6)).all():
        raise DatasetError("Target end is not t+6")
    report = {
        "observation_time_checks_pass": True,
        "checks": [
            "station_isolation",
            "exact_hour_reindex",
            "past_only_lags",
            "right_aligned_rolls",
            "same_station_t1_through_t6_targets",
            "all_six_future_hours",
            "trailing_30d_history",
            "training_only_spike_selection",
            "target_feature_allowlist",
            "chronological_aligned_splits",
            "six_hour_boundary_purge",
            "no_fitted_scaler_or_imputer",
        ],
        "operational_availability_pass": False,
        "operational_blockers": [
            "OpenAQ hourly data does not establish historical publication/revision availability.",
            (
                "ERA5-Land reanalysis at t was released after t; do not use it as "
                "a known-at-t operational predictor."
            ),
        ],
        "optional_fire": "deferred; exact event/availability contract tested separately",
        "optional_satellite": "deferred; no satellite predictor columns",
        "dataset_mode": "retrospective_research_not_operational_backtest",
    }
    if require_operational:
        raise DatasetError(
            "Operational availability leakage gate FAILED: historical "
            "publication times are unverified and ERA5 at t is retrospective"
        )
    return report


def feature_matrix(frame, features, require_operational=True):
    if any(c in TARGETS or c.startswith("future_") for c in features):
        raise DatasetError("Targets cannot enter features")
    if require_operational and not frame.publication_availability_verified.all():
        raise DatasetError("Cannot export operational features without as-of availability proof")
    return frame.loc[:, features].copy()


def regression(y, prediction):
    if len(y) == 0:
        return {"n": 0, "mae": None, "rmse": None}
    residual = np.asarray(y, dtype=float) - np.asarray(prediction, dtype=float)
    return {
        "n": len(y),
        "mae": float(np.abs(residual).mean()),
        "rmse": math.sqrt(float((residual**2).mean())),
    }


def classification(y, prediction):
    if len(y) == 0:
        return {"n": 0, "precision": None, "recall": None, "f1": None, "positive_prevalence": None}
    y, prediction = np.asarray(y, dtype=bool), np.asarray(prediction, dtype=bool)
    tp, fp, fn = (
        int((y & prediction).sum()),
        int((~y & prediction).sum()),
        int((y & ~prediction).sum()),
    )
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "n": len(y),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "positive_prevalence": float(y.mean()),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision_denominator_zero": tp + fp == 0,
        "recall_denominator_zero": tp + fn == 0,
    }


def baselines(frame, frozen):
    report = {
        "interpretation": (
            "Retrospective naive benchmarks only; publication availability is "
            "not verified. Not a prospective skill claim."
        ),
        "target": "future_max_pm25_6h",
        "unit": "µg/m³",
        "splits": {},
    }
    selected = frozen.get("selected")
    for split in ("train", "validation", "test"):
        group = frame[frame.split == split]

        def metrics(rows):
            shared = rows[rows.regression_eligible & rows.pm25_rolling_mean_6h.notna()]
            labels = rows[rows.spike_next_6h.notna()]
            high = (
                (labels.pm25_t >= labels[f"trailing_30d_p{selected['percentile']}_pm25"])
                if selected
                else []
            )
            return {
                "all_regression_eligible_n": int(rows.regression_eligible.sum()),
                "comparison_population": "same rows: current PM and complete six-hour rolling mean",
                "persistence": regression(shared.future_max_pm25_6h, shared.pm25_t),
                "recent_mean_6h": regression(
                    shared.future_max_pm25_6h, shared.pm25_rolling_mean_6h
                ),
                "always_negative": classification(labels.spike_next_6h, np.zeros(len(labels))),
                "current_high_pm25": classification(labels.spike_next_6h, high),
            }

        report["splits"][split] = {
            "pooled": metrics(group),
            "by_station": {
                str(station): metrics(rows) for station, rows in group.groupby("station_id")
            },
        }
    return report


def target_analysis(frame, frozen):
    result = {**frozen, "prevalence_after_freeze": {}}
    for split in ("train", "validation", "test"):
        labels = frame.loc[frame.split == split, "spike_next_6h"].dropna()
        result["prevalence_after_freeze"][split] = {
            "n": len(labels),
            "positive_rate": float(labels.mean()) if len(labels) else None,
        }
    return result


def holdout_plan(stations, config):
    return {
        "prepared_only_no_model_trained": True,
        "enabled": len(stations) >= 3,
        "held_out_station_id": sorted(str(s["id"]) for s in stations)[-1]
        if len(stations) >= 3
        else None,
        "selection": (
            "Highest sorted location ID, fixed before any model evaluation; "
            "not chosen by test scores."
        ),
        "boundaries": split_boundaries(config),
        "policy": (
            "Exclude held-out station from training and all fitting; use "
            "training periods on remaining stations. Evaluate its "
            "validation/test periods separately. Preserve chronological "
            "primary test."
        ),
    }
