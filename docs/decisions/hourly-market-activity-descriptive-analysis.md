---
type: Methodology Decision
title: Hourly market-activity descriptive analysis
description: Approved parameters for descriptive analysis of hourly Binance market activity.
tags: [binance, hourly, descriptive-analysis, market-activity]
status: stable
authority: approved-methodology
decision_status: approved
generated: { by: "process:okf-migration", at: "2026-09-29T10:16:31Z" }
verified: { by: "human:marcela-prata-silverio", at: "2026-09-29T10:16:31Z" }
sources:
  - id: analysis-config
    resource: ../../configs/binance_hourly_market_activity_descriptive_analysis.json
    title: Binance hourly market-activity descriptive-analysis configuration
  - id: analysis-notebook
    resource: ../../notebooks/09_binance_hourly_market_activity_descriptive_analysis.ipynb
    title: Binance hourly market-activity descriptive-analysis notebook
---

# Exploratory hourly market-activity descriptive analysis

Approved on 2026-09-16 as an extension of the descriptive-analysis stage:

- universe and source: all 40 pairs and each immutable canonical CSV from the
  approved expanded hourly collection;
- observation period: each pair's full observed span through
  2026-09-01 23:00 UTC;
- analyzed fields: `base_asset_volume`, `quote_asset_volume`,
  `number_of_trades`, `taker_buy_base_asset_volume`, and
  `taker_buy_quote_asset_volume` from each Binance hourly kline;
- units: base-asset quantities remain in the corresponding base asset,
  quote-asset quantities remain in USDT, and `number_of_trades` remains a
  count; values with different units are not combined;
- reported statistics: observation, missing-value, and zero counts; zero
  share; total; arithmetic mean; median; sample standard deviation and
  variance (`ddof=1`); minimum; first and third quartiles; maximum; range;
  interquartile range; coefficient of variation; sample skewness; and Fisher
  excess kurtosis;
- quartile and missing-data treatment: use linear interpolation at 25%, 50%,
  and 75%, with no interpolation, forward fill, backfill, or synthesis of
  source observations;
- visualization: one three-panel hourly activity figure per asset, separating
  base-asset volume, USDT quote volume, and number of trades, plus overview
  panels for USDT quote volume and trade count.

These measures describe exchange-reported activity aggregated inside each
hourly kline. They are not transaction-level records. Totals across assets are
not combined because base-asset quantities use different units, and comparing
full-sample totals requires caution because listing dates and observed spans
differ.
