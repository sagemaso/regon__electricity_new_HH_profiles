import pandas as pd
from pylpg import lpg_execution, lpgdata
import numpy as np
from pathlib import Path
import zlib

OUT_DIR = Path("generated_profiles")
OUT_DIR.mkdir(exist_ok=True)
(OUT_DIR / "sfh").mkdir(exist_ok=True)
(OUT_DIR / "mfh").mkdir(exist_ok=True)

def stable_seed_from_name(name: str) -> int:
    """Create a stable (reproducible) integer seed from a string."""
    return zlib.crc32(name.encode("utf-8")) & 0xffffffff  # 0..2^32-1

def get_all_household_types():
    """Alle Household-Typen als Strings auslesen."""
    return [
        getattr(lpgdata.Households, name)
        for name in dir(lpgdata.Households)
        if not name.startswith("__")
    ]


mapping = pd.read_csv("household_type_matching_census22_filled.csv", index_col="lpg_class")


def get_household_by_name(name: str):
    """
    Return the household object from lpgdata.Households by its name.

    Args:
        name (str): Name of the household, e.g., 'CHS01 Couple with 2 Children, Dad Employed'

    Returns:
        household object (JsonReference)
    """
    # Iterate all households and match by Name attribute
    for attr_name in dir(lpgdata.Households):
        if attr_name.startswith("__"):
            continue
        household = getattr(lpgdata.Households, attr_name)
        if household.Name == name:
            return household

    raise ValueError(f"Household with name '{name}' not found.")


def run():
    results = pd.DataFrame()
    for householddata_name in mapping[mapping.n_profiles > 0].index:
        print(householddata_name)

        for n_profile in range(mapping.loc[householddata_name, "n_profiles"]):
            random_seed = np.random.randint(0, 100000)
            df = lpg_execution.execute_lpg_single_household(
                2011,
                get_household_by_name(householddata_name),
                lpgdata.HouseTypes.HT20_Single_Family_House_no_heating_cooling,
                resolution="01:00:00",
                random_seed=random_seed,
                startdate="2011-01-01",
                enddate="2011-12-31"
            )
            results[householddata_name + "_sfh_seed_" + str(random_seed)] = df["Electricity_HH1"].resample(
                "15min").sum()

        for n_profile in range(mapping.loc[householddata_name, "n_profiles"]):
            random_seed = np.random.randint(0, 100000)
            df = lpg_execution.execute_lpg_single_household(
                2011,
                get_household_by_name(householddata_name),
                lpgdata.HouseTypes.HT22_Big_Multifamily_House_no_heating_cooling,
                resolution="01:00:00",
                random_seed=random_seed,
                startdate="2011-01-01",
                enddate="2011-12-31"
            )
            results[householddata_name + "_mfh_seed_" + str(random_seed)] = df["Electricity_HH1"].resample(
                "15min").sum()

    results.to_csv("resulting_profiles_all.csv")

    return results


def run_sfh():
    for householddata_name in mapping[mapping.n_profiles > 0].index:
        n_profiles = int(mapping.loc[householddata_name, "n_profiles"])
        n_profiles = min(n_profiles, 3)
        print(f"{householddata_name} -> {n_profiles} profiles (SFH)")

        # Reproducible RNG per household type
        rng = np.random.default_rng(stable_seed_from_name(householddata_name))

        for _ in range(n_profiles):
            random_seed = int(rng.integers(0, 100000))

            df = lpg_execution.execute_lpg_single_household(
                2011,
                get_household_by_name(householddata_name),
                lpgdata.HouseTypes.HT20_Single_Family_House_no_heating_cooling,
                resolution="01:00:00",
                random_seed=random_seed,
                startdate="2011-01-01",
                enddate="2011-12-31"
            )
            print("DEBUG len(df):", len(df))
            print("DEBUG first timestamps:", df.index[:5])
            print("DEBUG last timestamps:", df.index[-5:])
            print("DEBUG inferred step:", df.index.to_series().diff().dropna().mode().iloc[0])
            series_15min = df["Electricity_HH1"].resample("15min").sum()

            out_path = OUT_DIR / "sfh" / f"{householddata_name}_sfh_seed_{random_seed}.csv"
            series_15min.to_csv(out_path)


def run_mfh():
    for householddata_name in mapping[mapping.n_profiles > 0].index:
        n_profiles = int(mapping.loc[householddata_name, "n_profiles"])
        print(f"{householddata_name} -> {n_profiles} profiles (MFH)")

        # Reproducible RNG per household type
        rng = np.random.default_rng(stable_seed_from_name(householddata_name))

        for _ in range(n_profiles):
            random_seed = int(rng.integers(0, 100000))

            df = lpg_execution.execute_lpg_single_household(
                2011,
                get_household_by_name(householddata_name),
                lpgdata.HouseTypes.HT22_Big_Multifamily_House_no_heating_cooling,
                resolution="01:00:00",
                random_seed=random_seed,
                startdate="2011-01-01",
                enddate="2011-12-31"
            )
            print("DEBUG len(df):", len(df))
            print("DEBUG first timestamps:", df.index[:5])
            print("DEBUG last timestamps:", df.index[-5:])
            print("DEBUG inferred step:", df.index.to_series().diff().dropna().mode().iloc[0])
            series_15min = df["Electricity_HH1"].resample("15min").sum()

            out_path = OUT_DIR / "mfh" / f"{householddata_name}_mfh_seed_{random_seed}.csv"
            series_15min.to_csv(out_path)


def analyze():
    results = pd.read_csv("resulting_profiles_sfh.csv",
                          index_col=0,
                          parse_dates=True)  # automatically try to parse dates)

    results_mfh = pd.read_csv("resulting_profiles_mfh.csv",
                              index_col=0,
                              parse_dates=True)  # automatically try to parse dates)

    data = pd.concat([results, results_mfh], axis="columns")
    data.resample("1h").sum().mul(1 / data.sum())[168:2 * 168].plot(alpha=0.3, legend=False)
    data.sum(axis=1).resample("1h").sum().mul(
        1 / data.sum().sum())[168:2 * 168].plot(linestyle="--", color="black")

    results.sum(axis=1).resample("1h").sum()[168:2 * 168].plot(linestyle="--", color="black")


run_sfh()