#!/usr/bin/env python3
"""
Calculate the probability that at least one person in a household is employed,
based on household size distribution and household type from German census data.

Uses the formula: P(at least one employed) = sum over n of P(size=n|type) * (1 - (1-p_emp)^n)
where p_emp is the individual employment probability for that household type.
"""

import re
from pathlib import Path

import pandas as pd

from german_number_utils import parse_german_int
from text_utils import normalize_label


DATA_DIR = Path(__file__).parent
CENSUS_FILE = DATA_DIR / "5000H-2001_de.csv"


def load_household_size_distribution() -> pd.DataFrame:
    """
    Load census data: household size × household type.

    Returns:
        DataFrame with columns: date, hh_size, household_type, count, flag
    """
    df = pd.read_csv(
        CENSUS_FILE,
        sep=";",
        skiprows=6,
        header=None,
        names=["date", "hh_size", "household_type", "count", "flag"],
        dtype=str,
        encoding="utf-8-sig"
    )

    df["household_type"] = normalize_label(df["household_type"])
    df["hh_size"] = normalize_label(df["hh_size"])
    df["count"] = parse_german_int(df["count"].replace({"-": "0"}))

    return df


def parse_household_size(label) -> int | None:
    """
    Convert household size label to integer.

    Args:
        label: German size label like "1 Person", "6 und mehr Personen"

    Returns:
        Integer household size (6+ treated as 6), or None if unparseable
    """
    if pd.isna(label):
        return None
    label = str(label)
    if "6 und mehr" in label or "6 or more" in label.lower():
        return 6  # Conservative assumption: 6+ as 6
    match = re.match(r"(\d+)", label)
    if match:
        return int(match.group(1))
    return None


def calculate_size_probabilities(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate P(size=n | household_type) for each combination.

    Args:
        df: Raw census dataframe from load_household_size_distribution()

    Returns:
        DataFrame with columns: household_type, n, count, total, p_size
    """
    # Get total households per type (rows where hh_size == "Insgesamt")
    totals = (
        df[df["hh_size"] == "Insgesamt"]
        .set_index("household_type")["count"]
    )

    # Filter to actual size rows (exclude totals)
    size_df = df[
        (df["hh_size"] != "Insgesamt") &
        (df["household_type"] != "Insgesamt")
    ].copy()

    size_df["n"] = size_df["hh_size"].apply(parse_household_size)
    size_df = size_df[size_df["n"].notna()].copy()
    size_df["n"] = size_df["n"].astype(int)
    size_df["total"] = size_df["household_type"].map(totals)
    size_df["p_size"] = size_df["count"] / size_df["total"]

    return size_df[["household_type", "n", "count", "total", "p_size"]]


def prob_at_least_one_employed(
    size_probs: pd.DataFrame,
    household_type: str,
    p_individual_employed: float
) -> float:
    """
    Calculate probability that at least one household member is employed.

    Uses: P(>=1 employed) = sum_n P(size=n|type) * (1 - (1-p)^n)

    This assumes independence of employment status among household members,
    which is a simplification. The actual correlation is likely positive.

    Args:
        size_probs: DataFrame from calculate_size_probabilities()
        household_type: Household type label (e.g., "Paare ohne Kind(er)")
        p_individual_employed: Probability an individual is employed

    Returns:
        Probability that at least one person in the household is employed
    """
    subset = size_probs[size_probs["household_type"] == household_type]
    if subset.empty:
        raise ValueError(f"Unknown household type: {household_type}")

    # P(at least 1) = 1 - P(none) = 1 - (1-p)^n, weighted by size distribution
    prob = (subset["p_size"] * (1 - (1 - p_individual_employed) ** subset["n"])).sum()
    return float(prob)


def get_household_types(size_probs: pd.DataFrame) -> list[str]:
    """Get list of available household types."""
    return size_probs["household_type"].unique().tolist()


def main():
    """Example usage and demonstration."""
    print("Loading census data...")
    df = load_household_size_distribution()
    size_probs = calculate_size_probabilities(df)

    print("\nAvailable household types:")
    for hh_type in get_household_types(size_probs):
        print(f"  - {hh_type}")

    print("\n" + "=" * 70)
    print("Example: Probability of at least one employed person per household type")
    print("Assuming 50% individual employment probability (p=0.5)")
    print("=" * 70)

    p_employed = {
        "Einpersonenhaushalte (Singlehaushalte)": 0.5018,
        "Paare ohne Kind(er)": 0.5126,
        "Paare mit Kind(ern)": 0.5171,
        "Alleinerziehende Elternteile": 0.4316,
        "Mehrpersonenhaushalte ohne Kernfamilie": 0.6282,
    }

    for ht in get_household_types(size_probs):
        p = p_employed[ht]
        prob = prob_at_least_one_employed(size_probs, ht, p)
        print(f"{ht:45s}: {prob * 100:6.2f}%")

    print("\n" + "=" * 70)
    print("Size distribution for 'Paare mit Kind(ern)' (Couples with children):")
    print("=" * 70)
    couples_with_kids = size_probs[size_probs["household_type"] == "Paare mit Kind(ern)"]
    for _, row in couples_with_kids.iterrows():
        print(f"  {row['n']} persons: {row['p_size'] * 100:5.1f}% ({row['count']:,} households)")


if __name__ == "__main__":
    main()