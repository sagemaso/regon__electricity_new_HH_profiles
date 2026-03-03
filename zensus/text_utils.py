"""
Utilities for text normalization.
"""
import pandas as pd


def normalize_label(series: pd.Series) -> pd.Series:
    """
    Normalize text labels for comparison.

    Operations:
        - Convert to string
        - Replace non-breaking spaces with regular spaces
        - Strip leading/trailing whitespace
        - Collapse multiple whitespace characters to single space

    Args:
        series: Pandas Series with text labels

    Returns:
        Series with normalized strings
    """
    return (
        series.astype(str)
        .str.replace("\u00a0", " ", regex=False)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )