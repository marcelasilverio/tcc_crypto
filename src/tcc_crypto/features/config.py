"""Features: config."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from tcc_crypto.data.validation import PRICE_FIELDS
from tcc_crypto.features.catalog import ACTIVE_FEATURES
from tcc_crypto.modeling.config import (
    DailyFeatureSelectionConfig as DailyFeatureSelectionConfig,
)
from tcc_crypto.paths import DAILY_FEATURES_DIR


@dataclass(frozen=True)
class DailyFeatureConfig:
    """Validated settings for the approved daily feature set."""

    feature_set_id: str
    collection_config: Path
    interval: str
    time_zone: str
    missing_data_policy: str
    imputation_marker: str
    price_fields: tuple[str, ...]
    volume_field: str
    momentum_period: int
    rsi_period: int
    atr_period: int
    parabolic_sar_acceleration: float
    parabolic_sar_maximum: float
    parabolic_sar_verification_required: bool
    active_features: tuple[str, ...]
    features_requiring_verification: tuple[str, ...]
    feature_output_directory: Path
    analysis_output_directory: Path
    feature_selection: DailyFeatureSelectionConfig


def load_daily_feature_config(path: Path) -> DailyFeatureConfig:
    """Load and validate the daily feature configuration."""
    with path.open(encoding="utf-8") as config_file:
        payload = json.load(config_file)

    if payload["interval"] != "1d":
        raise ValueError("Daily features require the 1d interval.")
    if payload["time_zone"] != "UTC":
        raise ValueError("Daily features require UTC timestamps.")
    missing_data = payload["missing_data"]
    if missing_data["policy"] != "forward_fill_internal":
        raise ValueError("Daily features require forward_fill_internal.")
    if missing_data["imputation_marker"] != "is_imputed":
        raise ValueError("Daily features require the is_imputed audit marker.")
    if missing_data["raw_data_mutation"] is not False:
        raise ValueError("Raw daily data must remain immutable.")
    if missing_data["leading_fill"] is not False:
        raise ValueError("Leading daily gaps must not be filled.")
    if missing_data["trailing_fill"] is not False:
        raise ValueError("Trailing daily gaps must not be filled.")
    if tuple(payload["price_fields"]) != PRICE_FIELDS:
        raise ValueError(f"price_fields must be exactly {PRICE_FIELDS}.")
    if payload["volume_field"] != "quote_asset_volume":
        raise ValueError("Daily features require quote_asset_volume.")
    if int(payload["momentum_period"]) != 10:
        raise ValueError("The approved momentum period is 10 observations.")
    if int(payload["rsi_period"]) != 14:
        raise ValueError("The approved RSI period is 14 observations.")
    if int(payload["atr_period"]) != 14:
        raise ValueError("The approved ATR period is 14 observations.")
    parabolic_sar = payload["parabolic_sar"]
    if parabolic_sar["enabled"] is not True:
        raise ValueError("The provisionally approved Parabolic SAR must be enabled.")
    if float(parabolic_sar["acceleration"]) != 0.0:
        raise ValueError("Parabolic SAR acceleration must provisionally remain zero.")
    if float(parabolic_sar["maximum"]) != 0.0:
        raise ValueError("Parabolic SAR maximum must provisionally remain zero.")
    if parabolic_sar["verification_required"] is not True:
        raise ValueError("Parabolic SAR must remain marked for later verification.")
    if tuple(payload["active_features"]) != ACTIVE_FEATURES:
        raise ValueError("active_features does not match the approved feature order.")
    if tuple(payload["features_requiring_verification"]) != ("parabolic_sar",):
        raise ValueError("parabolic_sar must remain marked for verification.")
    selection = payload["feature_selection"]
    if selection["enabled"] is not True:
        raise ValueError("The approved daily feature selection must be enabled.")
    if float(selection["variance_threshold"]) != 0.01:
        raise ValueError("The approved variance threshold is 0.01.")
    if float(selection["correlation_threshold"]) != 0.8:
        raise ValueError("The approved correlation threshold is 0.8.")
    if selection["correlation_method"] != "pearson":
        raise ValueError("The approved correlation method is Pearson.")
    if tuple(selection["training_window_sizes"]) != (60, 75, 90):
        raise ValueError("The approved training windows are 60, 75, and 90 days.")
    if selection["window_type"] != "rolling":
        raise ValueError("The approved training windows are rolling.")
    if selection["refit_frequency"] != "every_prediction":
        raise ValueError("Feature selection must be refitted for every prediction.")
    if int(selection["prediction_step_observations"]) != 1:
        raise ValueError("The approved prediction step is one observation.")
    if selection["fit_scope"] != "training_only":
        raise ValueError("Feature selection must be fitted on training data only.")

    return DailyFeatureConfig(
        feature_set_id=str(payload["feature_set_id"]),
        collection_config=Path(payload["collection_config"]),
        interval="1d",
        time_zone="UTC",
        missing_data_policy="forward_fill_internal",
        imputation_marker="is_imputed",
        price_fields=PRICE_FIELDS,
        volume_field="quote_asset_volume",
        momentum_period=10,
        rsi_period=14,
        atr_period=14,
        parabolic_sar_acceleration=0.0,
        parabolic_sar_maximum=0.0,
        parabolic_sar_verification_required=True,
        active_features=ACTIVE_FEATURES,
        features_requiring_verification=("parabolic_sar",),
        feature_output_directory=Path(
            payload.get("feature_output_directory", DAILY_FEATURES_DIR)
        ),
        analysis_output_directory=Path(payload["analysis_output_directory"]),
        feature_selection=DailyFeatureSelectionConfig(
            variance_threshold=0.01,
            correlation_threshold=0.8,
            correlation_method="pearson",
            training_window_sizes=(60, 75, 90),
            window_type="rolling",
            refit_frequency="every_prediction",
            prediction_step_observations=1,
            fit_scope="training_only",
        ),
    )
