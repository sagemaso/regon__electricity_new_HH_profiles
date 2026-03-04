"""
Calculate derived household statistics from census data.

Computes:
    - Average household size per type
    - Probability-based proxy for households with at least one employed person
"""
import pandas as pd

from hh_retired import main as get_household_senior_data


def main():
    # Get household data with employment shares and senior status
    df = get_household_senior_data()

    # 1) Average household size per type
    df["avg_hh_size"] = df["total_persons"] / df["household_count"]

    # 2) Convert employed percentage to probability
    df["p_employed"] = df["employed"] / 100.0

    # 3) Proxy: Share of households with at least 1 employed person
    # Using binomial probability: P(at least 1) = 1 - P(none) = 1 - (1-p)^n
    df["hh_with_employed_proxy_pct"] = (1 - (1 - df["p_employed"]) ** df["avg_hh_size"]) * 100

    # 4) Format output with selected columns
    output_columns = [
        "household_type_norm",
        "household_count",
        "avg_hh_size",
        "employed",
        "hh_with_employed_proxy_pct",
        "unemployed",
        "not_in_labor_force",
        "under_min_age",
        "senior_only_pct",
        "senior_mixed_pct",
        "no_senior_pct",
    ]
    result = df[output_columns].copy()
    result["avg_hh_size"] = result["avg_hh_size"].round(3)
    result["hh_with_employed_proxy_pct"] = result["hh_with_employed_proxy_pct"].round(2)

    print("RESULT + Proxy 'Households with at least 1 employed person' (model-based):")
    print(result.to_string(index=False))

    return result


if __name__ == "__main__":
    main()