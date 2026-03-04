"""
Add senior household status shares to household employment data.

Data sources:
    - 5000H-1004_de.csv: Households by senior status
    - Employment/household data from hh_employment module
"""
from pathlib import Path

import pandas as pd

from hh_employment import main as get_household_employment_data

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
         .str.replace("\u00a0", "", regex=False)
         .str.replace(" ", "", regex=False)
         .str.replace(".", "", regex=False)
         .str.strip()
         .replace({"": None, "nan": None})
         .astype("Int64")
    )


def load_households_by_senior_status() -> pd.DataFrame:
    """Load households data by senior status (5000H-1004)."""
    df = read_census_semicolon(
        SCRIPT_DIR / "5000H-1004_de.csv",
        skiprows=6,
        column_names=["date", "senior_status", "count", "count_flag", "percent", "percent_flag"]
    )
    df["count_int"] = parse_german_int(df["count"])
    return df


def main():
    # --- 1) Load senior status data ---
    senior_df = load_households_by_senior_status()

    total_households = int(senior_df.loc[
        senior_df["senior_status"] == "Insgesamt", "count_int"
    ].iloc[0])

    # Filter out total row and calculate percentages
    senior_data = senior_df[senior_df["senior_status"] != "Insgesamt"].copy()
    senior_data["share_pct"] = (senior_data["count_int"] / total_households * 100).round(2)

    # Build senior status columns as a dict
    senior_columns = {
        "senior_only_pct": float(senior_data.loc[
            senior_data["senior_status"] == "Haushalte mit ausschließlich Senioren/-innen",
            "share_pct"
        ].iloc[0]),
        "senior_mixed_pct": float(senior_data.loc[
            senior_data["senior_status"] == "Haushalte mit Senioren/-innen und Jüngeren",
            "share_pct"
        ].iloc[0]),
        "no_senior_pct": float(senior_data.loc[
            senior_data["senior_status"] == "Haushalte ohne Senioren/-innen",
            "share_pct"
        ].iloc[0]),
    }

    print("Senior Status Shares (Germany total):")
    for key, value in senior_columns.items():
        print(f"  {key}: {value}%")

    # --- 2) Get household employment data and add senior columns ---
    household_data = get_household_employment_data()

    result = household_data.copy()
    for col_name, value in senior_columns.items():
        result[col_name] = value

    print("\nRESULT + Senior Status (Germany total, as additional columns):")
    print(result.to_string(index=False))

    return result


if __name__ == "__main__":
    main()