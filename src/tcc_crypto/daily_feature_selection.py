"""Compatibility imports; implementation lives in the domain packages."""

from tcc_crypto.features.warmup import (
    _validate_numeric_feature_frame as _validate_numeric_feature_frame,
)
from tcc_crypto.features.warmup import (
    remove_leading_feature_warmup as remove_leading_feature_warmup,
)
from tcc_crypto.modeling.selection import DailyFeatureSelector as DailyFeatureSelector
from tcc_crypto.modeling.selection import (
    RollingFeatureSelectionStep as RollingFeatureSelectionStep,
)
from tcc_crypto.modeling.selection import (
    RollingFeatureSelectionSummary as RollingFeatureSelectionSummary,
)
from tcc_crypto.modeling.selection import (
    iter_rolling_feature_selection as iter_rolling_feature_selection,
)
from tcc_crypto.modeling.selection import (
    summarize_rolling_feature_selection as summarize_rolling_feature_selection,
)
