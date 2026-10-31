"""Read the two experiment JSONs without creating execution artifacts."""

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.model_selection import ParameterGrid

from tcc_crypto.dataset import ACTIVE_FEATURES
from tcc_crypto.paths import CONFIG, ROOT, component


@dataclass(frozen=True)
class Config:
    values: dict
    grid: dict

    @property
    def signature(self) -> dict:
        return {"experiment": self.values, "grid": self.grid}

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(
            json.dumps(self.signature, sort_keys=True).encode()
        ).hexdigest()


def load_config(path: Path | str | None = None) -> Config:
    path = Path(path) if path is not None else ROOT / CONFIG
    payload = json.loads(path.read_text())
    grid = json.loads((path.parent / payload["grid_config"]).read_text())
    return validate_config(Config(payload, grid))


def validate_config(config: Config) -> Config:
    p = config.values
    required = {
        "experiment_id",
        "symbols",
        "excluded_symbols",
        "study",
        "collection",
        "features",
        "targets",
        "windows",
        "selection",
        "scaling",
        "cv",
        "metrics",
        "models",
        "single_class_training_policy",
        "comparison_observations",
        "random_seed",
        "grid_config",
    }
    if set(p) != required:
        raise ValueError(f"Configuration keys differ: {set(p) ^ required}")
    component(p["experiment_id"])
    if not p["symbols"] or len(set(p["symbols"])) != len(p["symbols"]):
        raise ValueError("Symbols must be nonempty and unique.")
    for symbol in p["symbols"]:
        component(symbol)
    if not set(p["excluded_symbols"]) <= set(p["symbols"]):
        raise ValueError("Excluded symbols must belong to the collection universe.")
    if p["collection"]["interval"] != "1d":
        raise ValueError("This experiment uses daily candles.")
    start, end, warmup = (
        pd.Timestamp(p["study"][k], tz="UTC") for k in ("start", "end", "warmup_start")
    )
    if not warmup <= start <= end:
        raise ValueError("Study and warm-up dates are not ordered.")
    if (
        pd.Timestamp(p["collection"]["start_time_utc"]) > warmup
        or pd.Timestamp(p["collection"]["end_time_utc"]) < end
    ):
        raise ValueError("Collection must cover warm-up and study dates.")
    if (
        not p["targets"]
        or any(not 0 < q < 1 for q in p["targets"])
        or len(set(p["targets"])) != len(p["targets"])
    ):
        raise ValueError(
            "Target thresholds must be unique fractions between zero and one."
        )
    if not p["windows"] or any(w < 6 or not isinstance(w, int) for w in p["windows"]):
        raise ValueError("Window sizes must support five temporal splits.")
    if p["cv"] != {"n_splits": 5, "max_train_size": None, "test_size": None, "gap": 0}:
        raise ValueError("Use the approved TimeSeriesSplit defaults.")
    if (
        p["single_class_training_policy"] != "record_no_prediction"
        or p["comparison_observations"] != "common_successful_dates"
    ):
        raise ValueError("Unsupported failure/comparison policy.")
    if not isinstance(p["random_seed"], int):
        raise ValueError("An explicit integer random seed is required.")
    if config.grid["selection"]["primary_metric"] != "f1":
        raise ValueError("The approved ranking metric is F1.")
    if config.grid["selection"]["tie_break_order"] != [
        "mean_precision_descending",
        "f1_standard_deviation_ascending",
        "mean_roc_auc_descending",
        "kernel_simplicity_linear_rbf_poly",
        "C_ascending",
        "parameter_grid_order",
    ]:
        raise ValueError("Unsupported candidate tie-break order.")
    if config.grid["selection"]["floating_point_tolerance"] < 0:
        raise ValueError("Candidate tolerance must be nonnegative.")
    features = p["features"]
    if features["active_features"] != list(ACTIVE_FEATURES):
        raise ValueError("Use the explicit approved feature order.")
    if features["volume_field"] != "quote_asset_volume" or [
        features[k] for k in ("momentum_period", "rsi_period", "atr_period")
    ] != [10, 14, 14]:
        raise ValueError(
            "Feature names require the approved periods and volume convention."
        )
    if p["collection"]["time_zone"] != "0":
        raise ValueError("Collection must use UTC.")
    if not 1 <= p["collection"]["limit"] <= 1000 or p["collection"]["max_workers"] < 1:
        raise ValueError("Invalid collection limits.")
    if p["models"] != [
        "tuned_svc",
        "default_svc",
        "always_negative",
        "training_class_frequency",
    ]:
        raise ValueError("Use all four approved comparison models in order.")
    if p["metrics"] != [
        "accuracy",
        "precision",
        "recall",
        "f1",
        "balanced_accuracy",
        "roc_auc",
        "average_precision",
    ]:
        raise ValueError("Use the approved classification metrics.")
    if p["scaling"] != {"with_mean": True, "with_std": True}:
        raise ValueError("Use standard centering and variance scaling.")
    variance = p["selection"]["variance_threshold"]
    correlation = p["selection"]["correlation_threshold"]
    if not math.isfinite(variance) or variance < 0 or not 0 < correlation <= 1:
        raise ValueError("Invalid selection thresholds.")
    if not list(ParameterGrid(config.grid["parameter_grid"])):
        raise ValueError("Empty SVM grid.")
    return config


def select_symbols(
    config: Config, symbols: list[str] | None = None, *, all_symbols=False
) -> list[str]:
    if bool(symbols) == bool(all_symbols):
        raise ValueError("Choose symbols or all_symbols explicitly.")
    selected = list(config.values["symbols"] if all_symbols else symbols)
    if len(set(selected)) != len(selected) or not set(selected) <= set(
        config.values["symbols"]
    ):
        raise ValueError("Unknown or repeated symbols.")
    return selected
