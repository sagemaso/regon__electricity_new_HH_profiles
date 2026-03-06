import pandas as pd
from pylpg import lpg_execution, lpgdata
import numpy as np


def get_all_household_types():
    """Alle Household-Typen als Strings auslesen."""
    return [
        getattr(lpgdata.Households, name)
        for name in dir(lpgdata.Households)
        if not name.startswith("__")
    ]


mapping = pd.read_csv("n_profiles_reweighted_999.csv", index_col="lpg_class")
PROFILE_COL = "n_profiles_new"
SIM_YEAR = 2022
STARTDATE = "2022-01-01"
ENDDATE = "2022-12-31"


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
    for householddata_name in mapping[mapping[PROFILE_COL] > 0].index:
        print(householddata_name)

        for n_profile in range(mapping.loc[householddata_name, [PROFILE_COL]]):
            random_seed = np.random.randint(0, 100000)
            df = lpg_execution.execute_lpg_single_household(
                SIM_YEAR,
                get_household_by_name(householddata_name),
                lpgdata.HouseTypes.HT20_Single_Family_House_no_heating_cooling,
                resolution="01:00:00",
                random_seed=random_seed,
                startdate=STARTDATE,
                enddate=ENDDATE
            )
            results[householddata_name + "_sfh_seed_" + str(random_seed)] = df["Electricity_HH1"].resample(
                "15min").sum()

        for n_profile in range(mapping.loc[householddata_name, [PROFILE_COL]]):
            random_seed = np.random.randint(0, 100000)
            df = lpg_execution.execute_lpg_single_household(
                SIM_YEAR,
                get_household_by_name(householddata_name),
                lpgdata.HouseTypes.HT22_Big_Multifamily_House_no_heating_cooling,
                resolution="01:00:00",
                random_seed=random_seed,
                startdate=STARTDATE,
                enddate=ENDDATE
            )
            results[householddata_name + "_mfh_seed_" + str(random_seed)] = df["Electricity_HH1"].resample(
                "15min").sum()

    results.to_csv("resulting_profiles_all.csv")

    return results


def run_sfh():
    results = pd.DataFrame()
    for householddata_name in mapping[mapping[PROFILE_COL] > 0].index:
        print(householddata_name)

        for n_profile in range(mapping.loc[householddata_name, [PROFILE_COL]]):
            random_seed = np.random.randint(0, 100000)
            df = lpg_execution.execute_lpg_single_household(
                SIM_YEAR,
                get_household_by_name(householddata_name),
                lpgdata.HouseTypes.HT20_Single_Family_House_no_heating_cooling,
                resolution="01:00:00",
                random_seed=random_seed,
                startdate=STARTDATE,
                enddate=ENDDATE
            )
            # results[householddata_name + "_sfh_seed_" + str(random_seed)] = df["Electricity_HH1"].resample("15min").sum()
            df["Electricity_HH1"].resample("15min").sum().to_csv(
                f"resulting_profiles_{householddata_name}_sfh_seed_{str(random_seed)}_all.csv")

    # results.to_csv("resulting_profiles_sfh_all.csv")

    return results


def run_mfh():
    results = pd.DataFrame()
    for householddata_name in mapping[mapping[PROFILE_COL] > 0].index:
        print(householddata_name)

        for n_profile in range(mapping.loc[householddata_name, [PROFILE_COL]]):
            random_seed = np.random.randint(0, 100000)
            df = lpg_execution.execute_lpg_single_household(
                SIM_YEAR,
                get_household_by_name(householddata_name),
                lpgdata.HouseTypes.HT22_Big_Multifamily_House_no_heating_cooling,
                resolution="01:00:00",
                random_seed=random_seed,
                startdate=STARTDATE,
                enddate=ENDDATE
            )
            # results[householddata_name + "_mfh_seed_" + str(random_seed)] = df["Electricity_HH1"].resample("15min").sum()
            df["Electricity_HH1"].resample("15min").sum().to_csv(
                f"resulting_profiles_{householddata_name}_mfh_seed_{str(random_seed)}_all.csv")

    # results.to_csv("resulting_profiles_mfh_all.csv")

    return results


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

if __name__ == "__main__":
    run()