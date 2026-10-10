# Approved methodology decisions

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
- [SVM pilot and hyperparameter-search plan](svm-pilot-and-hyperparameter-search.md) - Approved staged SVM experiment using a small default pilot before temporally valid hyperparameter search and full expansion.
