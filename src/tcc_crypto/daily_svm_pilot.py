"""Compatibility imports; implementation lives in the domain packages."""

from tcc_crypto.modeling.metrics import _binary_metrics as _binary_metrics
from tcc_crypto.modeling.pilot import DailySvmPilotResult as DailySvmPilotResult
from tcc_crypto.modeling.pilot import _validate_pilot_dataset as _validate_pilot_dataset
from tcc_crypto.modeling.pilot import (
    run_default_svc_rolling_pilot as run_default_svc_rolling_pilot,
)
from tcc_crypto.reporting.pilot import (
    write_daily_svm_pilot_results as write_daily_svm_pilot_results,
)
from tcc_crypto.reporting.provenance import _git_revision as _git_revision
from tcc_crypto.reporting.provenance import (
    _git_working_tree_dirty as _git_working_tree_dirty,
)
from tcc_crypto.reporting.provenance import _package_version as _package_version
