"""
Utilities for reading German census (Zensus) CSV files.
"""
import pandas as pd


def read_census_csv(path: str, skiprows: int, column_names: list[str]) -> pd.DataFrame:
    """
    Read a German census CSV file with semicolon delimiter.

    Args:
        path: Path to the CSV file
        skiprows: Number of header rows to skip
        column_names: List of column names to assign

    Returns:
        DataFrame with cleaned data (footer removed)
    """
    df = pd.read_csv(
        path,
        sep=";",
        skiprows=skiprows,
        header=None,
        names=column_names,
        dtype=str,
        encoding="utf-8-sig"  # Removes BOM character at start
    )

    # Remove footer: starts at the line with "__________"
    first_col = column_names[0]
    if (df[first_col] == "__________").any():
        cut_index = df.index[df[first_col] == "__________"][0]
        df = df.iloc[:cut_index].copy()

    return df