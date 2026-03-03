"""
Utilities for parsing German number formats.
"""
import pandas as pd


def parse_german_int(series: pd.Series) -> pd.Series:
    """
    Convert a German-formatted number string column to integers.

    Handles:
        - Thousand separators: '.' or space or non-breaking space
        - Empty values become NA

    Args:
        series: Pandas Series with German number strings

    Returns:
        Series with nullable Int64 dtype
    """
    return (
        series.astype(str)
        .str.replace("\u00a0", "", regex=False)  # non-breaking space
        .str.replace(" ", "", regex=False)
        .str.replace(".", "", regex=False)  # thousand separator
        .str.strip()
        .replace({"": None, "nan": None})
        .astype("Int64")
    )


def parse_german_float(series: pd.Series) -> pd.Series:
    """
    Convert a German-formatted decimal string column to floats.

    Handles:
        - Decimal separator: ',' -> '.'
        - Thousand separators: '.' or space removed
        - Empty values become NA

    Args:
        series: Pandas Series with German decimal strings (e.g., "12,3")

    Returns:
        Series with float dtype
    """
    return (
        series.astype(str)
        .str.replace("\u00a0", "", regex=False)  # non-breaking space
        .str.replace(" ", "", regex=False)
        .str.replace(".", "", regex=False)  # thousand separator
        .str.replace(",", ".", regex=False)  # decimal separator
        .str.strip()
        .replace({"": None, "nan": None})
        .astype(float)
    )