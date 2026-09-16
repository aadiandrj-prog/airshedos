import math
from types import SimpleNamespace

import numpy as np
import pandas as pd

from prediction.availability import (
    OPERATIONAL_V1,
    availability_manifest,
    validate_availability_manifest,
)
from prediction.common import DatasetError
from prediction.frame import (
    TARGETS,
    apply_spike_rule,
    construct,
    freeze_spike_rule,
    split_boundaries,
)


def validate(
    frame,
    aq,
    weather,
    stations,
    config,
    features,
    frozen,
    require_operational=False,
    feature_availability=None,
):
    if any(
        c in TARGETS or c.startswith("future_") or c in {"split", "regression_eligible"}
        for c in features
    ):
        raise DatasetError("Target/split leakage into feature matrix")
    availability = feature_availability or availability_manifest(features, config)
    validate_availability_manifest(availability, features, config)
    operational = config.profile == OPERATIONAL_V1
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
    if operational and not (frame.feature_observation_end <= frame.aq_feature_cutoff).all():
        raise DatasetError("AQ input timestamp exceeds availability cutoff")
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
        "operational_availability_pass": operational,
        "availability_assumption_verified_prospectively": False,
        "availability_status": "conditional_buffer_contract" if operational else "research_only",
        "feature_profile": config.profile,
        "aq_availability_buffer_hours": config.aq_availability_buffer_hours if operational else 0,
        "publication_limitations": [
            "OpenAQ hourly data does not establish historical publication/revision availability.",
            (
                "ERA5-Land reanalysis at t was released after t; do not use it as "
                "a known-at-t operational predictor."
            ),
        ],
        "optional_fire": "deferred; exact event/availability contract tested separately",
        "optional_satellite": "deferred; no satellite predictor columns",
        "dataset_mode": "conditional_operational_backtest"
        if operational
        else "retrospective_research_not_operational_backtest",
    }
    report["operational_blockers"] = [] if operational else report["publication_limitations"]
    if require_operational and not operational:
        raise DatasetError(
            "Operational availability leakage gate FAILED: historical "
            "publication times are unverified and ERA5 at t is retrospective"
        )
    return report


def feature_matrix(
    frame,
    features,
    require_operational=True,
    feature_availability=None,
    accept_conditional_availability=False,
):
    if any(c in TARGETS or c.startswith("future_") for c in features):
        raise DatasetError("Targets cannot enter features")
    if require_operational:
        if feature_availability is None:
            raise DatasetError("Feature availability manifest required for operational export")
        if feature_availability["profile"] != OPERATIONAL_V1:
            raise DatasetError("Research availability is not deployment-safe")
        buffer = feature_availability["aq_availability_buffer_hours"]
        validate_availability_manifest(
            feature_availability,
            features,
            SimpleNamespace(profile=OPERATIONAL_V1, aq_availability_buffer_hours=buffer),
        )
        if not frame.aq_availability_buffer_hours.eq(buffer).all():
            raise DatasetError("Frame buffer differs from availability manifest")
        if not (
            frame.feature_observation_end <= frame.timestamp - pd.Timedelta(hours=buffer)
        ).all():
            raise DatasetError("Input exceeds operational availability cutoff")
        entries = feature_availability["features"]
        if [item["feature_name"] for item in entries] != features:
            raise DatasetError("Feature manifest and actual columns disagree")
        if any(not item["deployment_safe"] for item in entries) or any(
            c.startswith("era5_") for c in features
        ):
            raise DatasetError("Unsafe feature in operational export")
        if not frame.feature_profile.eq(OPERATIONAL_V1).all():
            raise DatasetError("Frame profile differs from operational manifest")
        if not accept_conditional_availability:
            raise DatasetError("Explicit acknowledgment of conditional availability is required")
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
        "profile": frame.feature_profile.iloc[0],
        "unit": "µg/m³",
        "splits": {},
    }
    selected = frozen.get("selected")
    for split in ("train", "validation", "test"):
        group = frame[frame.split == split]
        if frame.feature_profile.eq(OPERATIONAL_V1).all():
            group = group[group.operational_eligible]

        def metrics(rows):
            primary = "pm25_latest_available" if "pm25_latest_available" in rows else "pm25_t"
            shared = rows[rows.regression_eligible & rows.pm25_rolling_mean_6h.notna()]
            labels = rows[rows.spike_next_6h.notna()]
            high = (
                (labels[primary] >= labels[f"trailing_30d_p{selected['percentile']}_pm25"])
                if selected
                else []
            )
            return {
                "all_regression_eligible_n": int(rows.regression_eligible.sum()),
                "comparison_population": "same rows: eligible PM and complete trailing mean",
                "persistence": regression(shared.future_max_pm25_6h, shared[primary]),
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
        mask = frame.split == split
        if frame.feature_profile.eq(OPERATIONAL_V1).all():
            mask &= frame.operational_eligible
        labels = frame.loc[mask, "spike_next_6h"].dropna()
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
        "spike_rule_policy": (
            "Refreeze any data-dependent spike rule using remaining training stations only; "
            "do not reuse the primary pooled rule for holdout evaluation."
        ),
        "policy": (
            "Exclude held-out station from training and all fitting; use "
            "training periods on remaining stations. Evaluate its "
            "validation/test periods separately. Preserve chronological "
            "primary test."
        ),
    }
