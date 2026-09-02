# Open decisions and source caveats

## Decision status

TCC I is a proposal and contains candidate choices rather than a fully frozen
protocol. The following items require explicit researcher approval and must be
recorded in `docs/methodology_decisions.md` and experiment configuration before
implementation.

| Topic | TCC I evidence | Required treatment |
|---|---|---|
| Asset universe | Binance spot cryptoassets; experiment figure mentions at least 15 assets | Define universe, minimum history, listing status, and eligibility rules |
| Quote asset | Not fixed | Approve the quote asset and pair-selection rule |
| Sample period | Not fixed | Approve start and end dates |
| Candle interval | Not fixed | Approve interval and annualization conventions |
| Holding window | Four days is proposed but explicitly described as changeable | Approve the exact horizon |
| Market capitalization | Appears in the experiment figure but not in the Binance kline data description | Remove it or approve a separate data source and timestamp-safe integration |
| Feature selection | Purpose is described, method is not | Approve method and search scope |
| SVM | Algorithm family is fixed | Approve kernel, hyperparameter space, tuning metric, and temporal validation |
| Temporal windows | Sliding windows are proposed | Approve train, validation, and test sizes, step, purge gap, and rolling versus expanding behavior |
| Markowitz model | Minimum variance and general risk-return optimization both appear | Approve objective, estimators, constraints, and solver behavior |
| Naive selection | Described only as non-predictive | Define the exact selection rule |
| Rebalancing | Not fixed | Approve frequency and execution timing |
| Empty signal | Not discussed | Define cash or fallback behavior |
| Trading frictions | Not discussed | Approve fees, slippage, liquidity, and minimum-order assumptions |
| Missing/listing data | Treatment is mentioned but not specified | Approve alignment, incomplete history, delisting, and missing-candle rules |
| Risk-free rate | Not discussed | Approve if a selected metric or objective requires it |

## Source inconsistencies that agents must not resolve silently

- The experiment figure lists market capitalization, while the data section
  describes Binance klines, which do not provide it.
- The figure says the portfolio selects at least 15 cryptocurrencies, but no
  universe or feasibility rule is defined.
- The text emphasizes a minimum-variance portfolio in one place and balancing
  expected return and risk in another.
- The source says the Binance response is chronological and then says it
  returns the most recent candles first. API ordering must be verified against
  the official API contract and tested.
- Daily candle boundary wording alternates between 00:00 and 00:01 UTC. The
  exchange timestamp must be treated as authoritative.
- Parabolic SAR parameters are printed as acceleration `0` and maximum `0`,
  which requires confirmation before implementation.
- The manuscript refers to a four-day window but also says it can change.
- The financial evaluation names cumulative and average return but does not
  fully define risk-adjusted metrics or transaction assumptions.

## Extraction caveats

- This Markdown set is an English structural translation and synthesis, not a
  line-by-line certified transcription.
- Page headers, footers, decorative elements, duplicated table headers, and one
  visible reviewer comment were intentionally omitted.
- Mathematical notation was normalized to plain Markdown-friendly text.
- The source PDF contains malformed internal object references, but all 69
  pages remained readable and the key methodology pages were visually checked.
- The related-work table and bibliography are summarized rather than reproduced
  in full. Consult the source PDF when exact citation wording is required.

## Agent rule

If an implementation task depends on any unresolved item above, stop and ask
the researcher. Do not convert a proposed value from TCC I into an approved
configuration merely because it appears in the manuscript.
