"""Data: gaps."""

from __future__ import annotations

import pandas as pd

from tcc_crypto.data.validation import PRICE_FIELDS, _validate_daily_values


def fill_internal_daily_gaps(values: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill missing UTC days bounded by observed daily candles.

    The input frame is not mutated. The returned ``is_imputed`` column records
    which rows were synthesized. Because the calendar spans only the first
    through last observed timestamps, this function never backfills pre-listing
    dates or extends an asset beyond its final observation.
    """
    _validate_daily_values(values, require_complete_calendar=False)
    complete_index = pd.date_range(
        start=values.index[0],
        end=values.index[-1],
        freq="D",
        tz="UTC",
        name=values.index.name,
    )
    imputed = ~complete_index.isin(values.index)
    aligned = values.reindex(complete_index).copy()
    aligned.loc[:, [*PRICE_FIELDS, "quote_asset_volume"]] = aligned.loc[
        :, [*PRICE_FIELDS, "quote_asset_volume"]
    ].ffill()
    aligned["is_imputed"] = imputed
    _validate_daily_values(aligned)
    return aligned
