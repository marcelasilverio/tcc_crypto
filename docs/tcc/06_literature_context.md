# Literature context

## Role of the review

The manuscript reports an initial ScienceDirect search using combinations of
“crypto”, “prediction”, “return”, “portfolio”, “allocation”, and “SVM”. From
253 identified papers, 18 studies were selected for the related-work table.
The review situates the project among cryptocurrency forecasting, volatility
modeling, anomaly detection, active trading, and portfolio research.

## Recurring findings in the reviewed studies

- Cryptocurrency prediction studies use daily, hourly, four-hour, and
  minute-level data; results are sensitive to both frequency and market regime.
- OHLCV-derived technical features are common, but several studies add
  macroeconomic, conventional-market, blockchain, search, news, or sentiment
  variables.
- SVM, neural networks, tree ensembles, fuzzy systems, econometric models, and
  hybrid architectures all appear; no single model dominates every dataset and
  horizon.
- Temporal splits and rolling out-of-sample evaluation are necessary because
  cryptocurrency distributions change over time.
- Survivorship bias, class balance, interpretability, and transaction realism
  materially affect conclusions.
- Prediction and portfolio construction are often studied separately, which
  supports this project's focus on their integration.

## Closest methodological anchors

The most direct design anchor is Paiva et al. (2019), which combines machine
learning with portfolio selection and compares an SVM-plus-mean-variance
strategy with simpler alternatives. Silva (2025) adapts this decision process
to feature construction, return targets, sliding windows, normalization, and
portfolio comparison. TCC I proposes adapting that lineage to Binance spot
cryptocurrencies.

Key references as listed in the manuscript:

- Paiva, Felipe Dias et al. (2019). “Decision-making for financial trading: A
  fusion approach of machine learning and portfolio selection.” *Expert Systems
  with Applications*, 115, 635-655.
- Silva, Ercilene Micaela Brito da (2025). *Decision-making in Ibovespa stock
  portfolio selection using machine learning*. Master's research proposal,
  CEFET-MG.
- Cortes, Corinna, and Vladimir Vapnik (1995). “Support-vector networks.”
  *Machine Learning*, 20, 273-297.
- Markowitz, Harry (1952). “Portfolio Selection.” *The Journal of Finance*,
  7(1), 77-91.
- Liu, Yukun, and Aleh Tsyvinski (2021). “Risks and returns of cryptocurrency.”
  *The Review of Financial Studies*, 34(6), 2689-2727.

## Related-work map

The 18-study table includes work by Raj et al. (2025), Parente et al. (2024),
Bagheri and Giudici (2025), Ozer and Sakar (2022), Dolatsara et al. (2022),
Harris et al. (2024), Pellicani et al. (2025), Bouteska et al. (2024), De Salve
et al. (2024), Goodell et al. (2023), Parvini et al. (2022), Maciel et al.
(2022), Cakici et al. (2024), Vieitez et al. (2024), Khosravi and Mirzaee
Ghazani (2023), Ren et al. (2022), Rezaei et al. (2021), and Izadi and
Hajizadeh (2025).

This map is contextual, not a quality assessment or an instruction to add the
external predictors used by those studies. Introducing a source beyond Binance
requires explicit approval.

## Source coverage

This document summarizes the related-work review on PDF pages 31-50 and retains
the principal references from the bibliography on PDF pages 60-69.
