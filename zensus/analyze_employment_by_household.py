"""
Analyze employment status distribution by household type using German census data.

Data sources:
    - 2000S-2005_de.csv: Persons by household type and employment status
    - 5000H-1004_de.csv: Households by senior status
"""
import pandas as pd

from census_io import read_census_csv
from german_number_utils import parse_german_int, parse_german_float
from text_utils import normalize_label


def load_persons_by_household_and_employment() -> pd.DataFrame:
    """Load persons data: household type x employment status."""
    return read_census_csv(
        "2000S-2005_de.csv",
        skiprows=6,
        column_names=["date", "household_type", "employment_status", "count", "flag"]
    )


def load_households_by_senior_status() -> pd.DataFrame:
    """Load households data: by senior status."""
    return read_census_csv(
        "5000H-1004_de.csv",
        skiprows=6,
        column_names=["date", "senior_status", "count", "count_flag", "percent", "percent_flag"]
    )


# Mapping from detailed employment status to simplified groups
EMPLOYMENT_STATUS_MAP = {
    "Erwerbstätige": "employed",
    "Erwerbslose": "unemployed",
    "Schüler/-innen u. Studierende (nicht erwerbsaktiv)": "not_in_labor_force",
    "Empfänger/-innen von Ruhegehalt/Kapitalerträgen": "not_in_labor_force",
    "Sonstige": "not_in_labor_force",
    "Personen unterhalb des Mindestalters": "under_min_age",
    # These are subtotals, exclude from analysis
    "Insgesamt": None,
    "Erwerbspersonen": None,
    "Nichterwerbspersonen": None,
}


def main():
    # Load data
    persons_df = load_persons_by_household_and_employment()
    households_df = load_households_by_senior_status()

    # Parse numeric columns
    persons_df["count_int"] = parse_german_int(persons_df["count"])
    households_df["count_int"] = parse_german_int(households_df["count"])

    if "percent" in households_df.columns:
        households_df["percent_float"] = parse_german_float(households_df["percent"])

    # Print data overview
    print("=== Persons by Household Type & Employment (2000S-2005) ===")
    print(persons_df.head(10))
    print(f"\nUnique household types (sample): {persons_df['household_type'].dropna().unique()[:10].tolist()}")

    print("\n=== Households by Senior Status (5000H-1004) ===")
    print(households_df.head(10))
    print(f"\nUnique senior status values: {households_df['senior_status'].dropna().unique().tolist()}")

    # Check for missing values
    print(f"\nMissing count_int in persons_df: {persons_df['count_int'].isna().sum()} of {len(persons_df)}")
    print(f"Missing count_int in households_df: {households_df['count_int'].isna().sum()} of {len(households_df)}")

    # List all employment status values
    statuses = sorted(persons_df["employment_status"].dropna().unique())
    print("\nEmployment status values (all):")
    for status in statuses:
        print(f"  - {status}")

    # Senior status breakdown
    total_households = int(households_df.loc[
        households_df["senior_status"] == "Insgesamt", "count_int"
    ].iloc[0])

    print(f"\nSenior Status Breakdown (total households: {total_households:,}):")
    for _, row in households_df.iterrows():
        if row["senior_status"] == "Insgesamt":
            continue
        n = int(row["count_int"])
        pct = n / total_households * 100
        print(f"  - {row['senior_status']}: {n:,} ({pct:.2f}%)")

    # Normalize labels and compute employment shares by household type
    df = persons_df.copy()
    df["employment_status_norm"] = normalize_label(df["employment_status"])
    df["household_type_norm"] = normalize_label(df["household_type"])

    print("\nNormalized employment status values:")
    for status in sorted(df["employment_status_norm"].dropna().unique()):
        print(f"  - {status}")

    # Map to simplified groups
    df["group"] = df["employment_status_norm"].map(EMPLOYMENT_STATUS_MAP)

    # Keep only rows with valid groups
    df_filtered = df.dropna(subset=["group"]).copy()
    print(f"\nRows after filtering (should be > 0): {len(df_filtered)}")

    # Aggregate by household type and group
    by_type_and_group = (
        df_filtered.groupby(["household_type_norm", "group"], as_index=False)["count_int"]
        .sum()
    )

    totals_by_type = (
        by_type_and_group.groupby("household_type_norm", as_index=False)["count_int"]
        .sum()
        .rename(columns={"count_int": "total_persons"})
    )

    result = by_type_and_group.merge(totals_by_type, on="household_type_norm", how="left")
    result["share"] = result["count_int"] / result["total_persons"]

    # Pivot to get shares by group as columns
    pivot = (
        result.pivot(index="household_type_norm", columns="group", values="share")
        .fillna(0)
    )

    pivot = pivot.merge(
        totals_by_type.set_index("household_type_norm"),
        left_index=True,
        right_index=True,
        how="left"
    )

    # Convert to percentages for display
    pivot_pct = (pivot.drop(columns=["total_persons"]) * 100).round(2)

    print("\n=== Employment Shares (%) by Household Type ===")
    print(pivot_pct.to_string())

    print("\n=== Total Persons by Household Type ===")
    print(pivot["total_persons"].astype("Int64").to_string())


if __name__ == "__main__":
    main()