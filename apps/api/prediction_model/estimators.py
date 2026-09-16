"""Deterministic CPU estimators; fitting never sees validation/test preprocessing statistics."""

import importlib.metadata
import platform

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from xgboost import XGBRegressor

from prediction.common import DatasetError
from prediction_model.data import TARGET, matrix
from prediction_model.metrics import nonnegative


def versions():
    return {
        "python": platform.python_version(),
        **{
            name: importlib.metadata.version(name)
            for name in [
                "numpy",
                "pandas",
                "pyarrow",
                "scikit-learn",
                "scipy",
                "xgboost",
                "joblib",
                "threadpoolctl",
            ]
        },
    }


def weights(train, policy):
    if not train.split.eq("train").all():
        raise DatasetError("Weights and fitting accept training rows only")
    if policy == "unweighted":
        return np.ones(len(train))
    if policy != "station_balanced":
        raise DatasetError("Unknown weighting policy")
    counts = train.station_id.value_counts()
    return (len(train) / (len(counts) * train.station_id.map(counts))).to_numpy()


def estimator(config, seed):
    family, params = config["family"], config["parameters"]
    if family == "ridge":
        return Pipeline(
            [
                (
                    "impute",
                    SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
                ),
                ("scale", StandardScaler()),
                ("model", Ridge(**params, solver="svd")),
            ]
        )
    if family == "hist_gradient_boosting":
        return HistGradientBoostingRegressor(
            **params, early_stopping=False, random_state=seed, loss="squared_error"
        )
    if family == "xgboost":
        return XGBRegressor(
            **params,
            random_state=seed,
            n_jobs=1,
            tree_method="hist",
            device="cpu",
            objective="reg:squarederror",
        )
    raise DatasetError("Unknown model family")


def fit(train, features, config, seed=42):
    if train.empty or not train.split.eq("train").all():
        raise DatasetError("Fitting accepts nonempty TRAIN only")
    if train[TARGET].isna().any():
        raise DatasetError("Targets cannot be imputed")
    x = matrix(train, features)
    y = train[TARGET].to_numpy()
    if config["transform"] == "log1p":
        y = np.log1p(y)
    elif config["transform"] != "raw":
        raise DatasetError("Unsupported target transformation")
    w = weights(train, config["weighting"])
    model = estimator(config, seed)
    # Ridge medians are unweighted training medians; scaling and loss use training weights.
    kwargs = (
        {"scale__sample_weight": w, "model__sample_weight": w}
        if config["family"] == "ridge"
        else {"sample_weight": w}
    )
    with threadpool_limits(limits=1):
        model.fit(x, y, **kwargs)
    return {"estimator": model, "features": features, "config": config, "seed": seed}


def predict(bundle, rows):
    with threadpool_limits(limits=1):
        raw = bundle["estimator"].predict(matrix(rows, bundle["features"]))
    if bundle["config"]["transform"] == "log1p":
        raw = np.expm1(raw)
    clipped, count = nonnegative(raw)
    return clipped, count
