"""Explicit UTC timestamp parsing shared by configurations."""

import pandas as pd


def _parse_utc_timestamp(value: object, field_name: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise ValueError(f"{field_name} must include an explicit UTC offset.")
    return timestamp.tz_convert("UTC")


def _parse_utc_day(value: object, field_name: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise ValueError(f"{field_name} must include an explicit UTC offset.")
    timestamp = timestamp.tz_convert("UTC")
    if timestamp != timestamp.normalize():
        raise ValueError(f"{field_name} must be aligned to a UTC day.")
    return timestamp
