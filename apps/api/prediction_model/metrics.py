"""Real-unit, equal-station and predeclared slice evaluation; never probability outputs."""

import numpy as np
import pandas as pd

from prediction.common import DatasetError
from prediction.evaluation import classification
from prediction_model.data import TARGET


def nonnegative(values):
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all():
        raise DatasetError("Nonfinite prediction")
    return np.maximum(values, 0), int((values < 0).sum())


def regression(y, pred):
    y, pred = np.asarray(y, dtype=float), np.asarray(pred, dtype=float)
    if len(y) != len(pred) or not np.isfinite(y).all() or not np.isfinite(pred).all():
        raise DatasetError("Invalid metric inputs")
    if len(y) == 0:
        return {"n": 0, "mae": None, "rmse": None, "bias": None, "underprediction_rate": None}
    error = pred - y
    return {
        "n": len(y),
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "bias": float(error.mean()),
        "underprediction_rate": float((error < 0).mean()),
    }


def spike_prediction(rows, pred):
    valid = rows.trailing_30d_p85_pm25.notna() & rows.spike_next_6h.notna()
    latest = rows.pm25_latest_available.to_numpy()
    predicted = (
        (pred >= rows.trailing_30d_p85_pm25.to_numpy()) & (pred >= latest * 1.30) & (pred > latest)
    )
    report = classification(rows.loc[valid, "spike_next_6h"], predicted[valid])
    report["tn"] = int((~rows.loc[valid, "spike_next_6h"].astype(bool) & ~predicted[valid]).sum())
    report["unavailable_labels"] = int((~valid).sum())
    return report


def evaluate(rows, pred, thresholds):
    pred, clipped = nonnegative(pred)
    frame = rows.reset_index(drop=True).copy()
    frame["prediction"] = pred

    def grouped(key):
        return {
            str(k): regression(g[TARGET], g.prediction)
            for k, g in frame.groupby(key, observed=False)
        }

    station = grouped("station_id")
    frame["period"] = frame.timestamp.dt.strftime("%Y-%m")
    frame["target_band"] = pd.cut(
        frame[TARGET], [-np.inf, *thresholds, np.inf], labels=["lower", "medium", "high", "extreme"]
    )
    high = frame[frame[TARGET] > thresholds[1]]
    return {
        "pooled": regression(frame[TARGET], pred),
        "macro_station_mae": float(np.mean([x["mae"] for x in station.values()])),
        "macro_station_rmse": float(np.mean([x["rmse"] for x in station.values()])),
        "by_station": station,
        "by_local_hour": grouped("hour_of_day"),
        "by_month": grouped("period"),
        "by_target_band": grouped("target_band"),
        "high_pollution": {"threshold": thresholds[1], **regression(high[TARGET], high.prediction)},
        "derived_spike": spike_prediction(frame, pred),
        "negative_predictions_clipped": clipped,
    }


def qualifies(candidate, baseline, policy):
    shared = set(candidate["by_station"]) & set(baseline["by_station"])
    station_ok = all(
        candidate["by_station"][s]["mae"]
        <= baseline["by_station"][s]["mae"] * policy["station_catastrophe_ratio"]
        + policy["station_catastrophe_allowance"]
        for s in shared
    )
    improved = sum(
        candidate["by_station"][s]["mae"] < baseline["by_station"][s]["mae"] for s in shared
    )
    checks = {
        "macro_improvement": candidate["macro_station_mae"]
        <= baseline["macro_station_mae"] * (1 - policy["minimum_macro_improvement_fraction"]),
        "pooled_not_materially_worse": candidate["pooled"]["mae"]
        <= baseline["pooled"]["mae"] * (1 + policy["maximum_pooled_worsening_fraction"]),
        "no_catastrophic_station": station_ok,
        "majority_stations_improve": bool(shared)
        and improved / len(shared) >= policy["minimum_fraction_stations_improved"],
        "same_stations": set(candidate["by_station"]) == set(baseline["by_station"]),
    }
    return {"eligible": all(checks.values()), "checks": checks}
