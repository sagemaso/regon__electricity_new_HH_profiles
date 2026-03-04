"""
Merge household type data with employment shares from census data.

Data sources:
    - 5000H-1006_de.csv: Households by household type
    - Employment pivot from analyze_employment_by_household module
"""
from pathlib import Path

import pandas as pd

from analyze_employment_by_household import get_employment_pivot

SCRIPT_DIR = Path(__file__).parent


def read_census_semicolon(path, skiprows: int, column_names: list[str]) -> pd.DataFrame:
    """Read a German census CSV file with semicolon delimiter."""
    df = pd.read_csv(
        path,
        sep=";",
        skiprows=skiprows,
        header=None,
        names=column_names,
        dtype=str,
        encoding="utf-8-sig"
    )
    # Remove footer rows (starts with "__________")
    if (df[column_names[0]] == "__________").any():
        cut_index = df.index[df[column_names[0]] == "__________"][0]
        df = df.iloc[:cut_index].copy()
    return df


def parse_german_int(s: pd.Series) -> pd.Series:
    """Parse German-formatted integers (dots as thousands separators)."""
    return (
        s.astype(str)
         .str.replace("\u00a0", "", regex=False)  # non-breaking space
         .str.replace(" ", "", regex=False)
         .str.replace(".", "", regex=False)  # thousands separator
         .str.strip()
         .replace({"": None, "nan": None})
         .astype("Int64")
    )


def normalize_label(s: pd.Series) -> pd.Series:
    """Normalize text labels by collapsing whitespace."""
    return (
        s.astype(str)
         .str.replace("\u00a0", " ", regex=False)
         .str.strip()
         .str.replace(r"\s+", " ", regex=True)
    )


def main():
    # --- 1) Load households by household type (5000H-1006) ---
    households_by_type = read_census_semicolon(
        SCRIPT_DIR / "5000H-1006_de.csv",
        skiprows=6,
        column_names=["date", "household_type", "count", "count_flag", "percent", "percent_flag"]
    )
    households_by_type["household_type_norm"] = normalize_label(households_by_type["household_type"])
    households_by_type["household_count"] = parse_german_int(households_by_type["count"])

    # Keep only relevant columns
    households = households_by_type[["household_type_norm", "household_count"]].copy()

    print("5000H-1006 Household Types (normalized):")
    print(households.to_string(index=False))

    # --- 2) Get employment shares by household type ---
    pivot, pivot_pct = get_employment_pivot()

    # Prepare employment percentages for merge
    employment_shares = pivot_pct.copy()
    employment_shares.index.name = "household_type_norm"
    employment_shares = employment_shares.reset_index()

    # Prepare total persons by household type
    total_persons = pivot["total_persons"].astype("Int64").reset_index()
    total_persons.columns = ["household_type_norm", "total_persons"]

    # --- 3) Merge: household type -> household count + employment shares ---
    result = (
        households.merge(employment_shares, on="household_type_norm", how="left")
                  .merge(total_persons, on="household_type_norm", how="left")
    )

    # Sort with "Insgesamt" (total) at the top
    result["sort_key"] = (result["household_type_norm"] != "Insgesamt").astype(int)
    result = result.sort_values(["sort_key", "household_type_norm"]).drop(columns=["sort_key"])

    print("\nRESULT (Household Type -> Household Count + Employment Shares):")
    print(result.to_string(index=False))

    return result


if __name__ == "__main__":
    main()