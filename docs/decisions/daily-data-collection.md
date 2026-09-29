---
type: Methodology Decision
title: Daily data collection
description: Approved parameters for collecting daily klines for the expanded 40-pair universe.
tags: [binance, data-collection, daily, asset-universe]
status: stable
authority: approved-methodology
decision_status: approved
generated: { by: "process:okf-migration", at: "2026-09-29T10:16:31Z" }
verified: { by: "human:marcela-prata-silverio", at: "2026-09-29T10:16:31Z" }
sources:
  - id: daily-collection-config
    resource: ../../configs/binance_selected_usdt_daily_collection.json
    title: Binance selected USDT daily collection configuration
---

# Daily collection for the expanded 40-pair universe

Approved on 2026-09-20 for subsequent data collection:

- replace the hourly candle interval with daily (`1d`) candles aligned to UTC;
- retain the approved expanded universe of 40 pairs and its ranking order;
- retain the requested range from 2017-01-01 00:00:00 UTC through
  2026-09-01 23:59:59.999 UTC;
- retain the Binance Spot endpoint, quote asset, selection source, selection
  rules, listing treatment, immutable raw format, checkpoint behavior,
  provenance outputs, and validation principles from the hourly collection;
- store the daily collection separately under `data/raw/binance/spot/1d/`,
  without modifying or replacing the existing hourly artifacts;
- report missing UTC-day openings within each pair's observed span, without
  synthesizing observations before listing or across gaps;
- interpret the nominal daily candle duration as 86,400,000 milliseconds;
  preserve shorter positive-duration candles for review and reject candles
  whose close precedes the open or exceeds the nominal daily window.

This change approves the collection frequency only. It does not automatically
approve daily feature definitions, target holding windows, rebalance frequency,
or modeling and backtesting parameters. Those choices remain separate
methodological decisions.
