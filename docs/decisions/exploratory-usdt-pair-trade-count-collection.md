---
type: Methodology Decision
title: Exploratory USDT pair trade-count collection
description: Approved parameters for the exploratory Binance USDT pair trade-count collection.
tags: [binance, data-collection, exploratory-analysis, trade-count]
status: stable
authority: approved-methodology
decision_status: approved
generated: { by: "process:okf-migration", at: "2026-09-29T10:16:31Z" }
verified: { by: "human:marcela-prata-silverio", at: "2026-09-29T10:16:31Z" }
sources:
  - id: trade-count-notebook
    resource: ../../notebooks/04_binance_usdt_quote_pair_trade_count.ipynb
    title: Binance USDT quote-pair trade-count notebook
---

# Exploratory USDT pair trade-count collection

Approved on 2026-09-02 for the exploratory notebook
`notebooks/04_binance_usdt_quote_pair_trade_count.ipynb`:

- market: Binance Spot;
- quote asset: USDT;
- observation start: 2017-01-01 00:00:00 UTC;
- observation end: the end of the previous UTC calendar day at execution time;
- interval used for aggregation: daily (`1d`) klines;
- activity measure: the sum of Binance's `number_of_trades` kline field for
  each trading symbol;
- symbol-status treatment: do not filter the symbols returned by the current
  `/api/v3/exchangeInfo` response by status;
- timezone: UTC.

This is an exploratory data-collection decision and does not freeze the final
experimental asset universe or sample period.

The symbol universe is limited to records present in the current
`exchangeInfo` response. Binance describes that endpoint as current exchange
information, so this procedure must not be described as a complete historical
catalog of symbols that were removed from the response. A separate approved
historical-symbol source would be required to make that stronger claim.
