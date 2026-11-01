# Approved methodology decisions

The October 31 block-window decision, including the November 1 correction
requiring normalization before feature selection, is the current authority for the revised
experiment. Earlier decisions retain historical provenance and explicit revision
notices. The active implementation follows the new block protocol; previous
configurations and evidence are retained in Git history.

The effective configuration names the complete scaling, selection and classifier
sequence `pipeline_order` and the internal temporal validation settings
`temporal_cross_validation`.

- [Daily experiment implementation and consultation guide](daily-code-organization.md) - Approved eight-module implementation, two configurations, stage commands, CSV dictionary with the `__NULL__` missing-value marker and Git-based historical retention.
- [CSV artifact organization by execution](csv-artifact-organization.md) - Approved shallow data and result layout using CSV tables without parallel Excel exports, with preserved historical evidence.
- [Daily block-window SVM experiment](daily-block-window-experiment.md) - October 31 revision defining raw availability, candle treatment, consecutive training and validation blocks, and integrated temporal SVM search.
- [Daily block-window experiment diagram](daily-block-window-experiment-diagram.md) - Visual map of the revised data preparation, per-window SVM training, validation and audit outputs.

- [Exploratory USDT pair trade-count collection](exploratory-usdt-pair-trade-count-collection.md) - Approved parameters for the exploratory Binance USDT pair trade-count collection.
- [Hourly data-collection universe](hourly-data-collection-universe.md) - Approved initial and expanded universes for Binance USDT hourly kline collection.
- [Daily data collection](daily-data-collection.md) - Approved parameters for collecting daily klines for the expanded 40-pair universe.
- [Hourly open-price correlation](hourly-open-price-correlation.md) - Approved parameters for exploratory correlation of hourly Binance opening prices.
- [Hourly high-to-open return correlation](hourly-high-open-return-correlation.md) - Approved parameters for exploratory correlation of hourly high-to-open returns.
- [Hourly price descriptive analysis](hourly-price-descriptive-analysis.md) - Approved parameters for descriptive analysis of hourly Binance price fields.
- [Hourly market-activity descriptive analysis](hourly-market-activity-descriptive-analysis.md) - Approved parameters for descriptive analysis of hourly Binance market activity.
- [Daily price and volume descriptive analysis](daily-price-volume-descriptive-analysis.md) - Approved parameters for descriptive analysis of daily Binance prices and USDT volume.
- [Daily Silva-derived feature set](daily-silva-feature-set.md) - Approved initial daily feature construction adapted from Silva 2026, with Parabolic SAR parameter verification pending.
- [Daily rolling feature selection](daily-feature-selection.md) - Approved variance and correlation filters refitted within every daily rolling training window.
- [Daily experiment period and internal-gap treatment](daily-sample-and-missing-data.md) - Approved experiment start, feature warm-up period, and forward-fill rule for internal daily gaps.
- [Daily next-day binary targets and same-day exit](daily-binary-targets-and-holding-period.md) - Approved target thresholds and alignment from day-t inputs to the next day's D0 high-to-open outcome and same-day exit.
- [SVM pilot and hyperparameter-search plan](svm-pilot-and-hyperparameter-search.md) - Approved staged SVM experiment using a BTCUSDT 2019H2 default pilot before temporally valid hyperparameter search and full expansion.
- [Temporal SVM grid search and final evaluation](svm-temporal-grid-search-and-final-evaluation.md) - Approved conditional SVC search, nested temporal model-selection structure, frozen-parameter walk-forward test, and classifier performance reporting.
- [Daily SVM asset eligibility](daily-svm-asset-eligibility.md) - Approved ex-post candidate universe, dynamic history requirement, per-asset model search, and LUNAUSDT exclusion for the daily SVM classification experiment.
- [Final SVM evaluation with single-class training windows](svm-final-evaluation-single-class-windows.md) - Approved omission and common-date comparison policy when a final walk-forward training window cannot fit an SVC.

- [Git-only retention of historical experiment files](git-only-history-retention.md) - Approved removal of superseded local artifacts and reports while preserving raw data and historical Git references.
