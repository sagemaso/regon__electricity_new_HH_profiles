import pandas as pd
import numpy as np

# -----------------------
# Settings (inputs)
# -----------------------
MAPPING_CSV = "/home/sarah/PycharmProjects/new_HH_profiles/household_type_matching_census22.csv"
HH_COUNTS_CSV = "/home/sarah/PycharmProjects/new_HH_profiles/hh_counts_de.csv"

# Target: total number of profiles in the pool
N_TOTAL = 10_000

# Optional: minimum number of profiles per egon_class (0 = purely proportional)
MIN_PER_CLASS = 0

# Output file (new mapping; original stays unchanged)
OUT_CSV = "/home/sarah/PycharmProjects/new_HH_profiles/household_type_matching_census22_filled.csv"

# -----------------------
# 1) Load files
# -----------------------
mapping = pd.read_csv(MAPPING_CSV)
hh = pd.read_csv(HH_COUNTS_CSV)

# -----------------------
# 2) Prepare data
# -----------------------
# Ensure hh_count_de is numeric
hh["hh_count_de"] = pd.to_numeric(hh["hh_count_de"], errors="raise")

# Use egon_class as index for easy alignment
hh = hh.set_index("egon_class")

# Rows in the mapping with egon_class == None/NaN must NOT be assigned profiles.
# Therefore, only keep classes that actually occur in the mapping (excluding NaN).
mapping_classes = set(mapping["egon_class"].dropna().unique())
hh = hh.loc[hh.index.intersection(mapping_classes)].copy()

# -----------------------
# 3) Compute proportional n_profiles per egon_class
# -----------------------
total_hh = hh["hh_count_de"].sum()
shares = hh["hh_count_de"] / total_hh          # class shares (0..1)

raw = shares * N_TOTAL                          # ideal (non-integer) profile counts
n = np.floor(raw).astype(int)                   # start with floor to get integers

# Apply minimum (optional)
if MIN_PER_CLASS > 0:
    n = np.maximum(n, MIN_PER_CLASS)

# Fix rounding so that sum(n) == N_TOTAL using largest remainders
current_sum = int(n.sum())
frac = raw - np.floor(raw)                      # fractional parts (remainders)

if current_sum < N_TOTAL:
    missing = N_TOTAL - current_sum
    add_idx = frac.sort_values(ascending=False).head(missing).index
    n.loc[add_idx] += 1
elif current_sum > N_TOTAL:
    extra = current_sum - N_TOTAL
    # Remove from smallest remainders first, but never go below MIN_PER_CLASS
    order = frac.sort_values(ascending=True).index.tolist()
    for ec in order:
        if extra == 0:
            break
        if MIN_PER_CLASS > 0 and n.loc[ec] <= MIN_PER_CLASS:
            continue
        n.loc[ec] -= 1
        extra -= 1

hh["n_profiles_class"] = n

# -----------------------
# 4) Distribute n_profiles_class over lpg_class rows in the mapping
# -----------------------
mapping["n_profiles"] = 0  # reset everything

for ec, n_class in hh["n_profiles_class"].items():
    idx = mapping.index[mapping["egon_class"] == ec].to_list()
    if not idx:
        continue

    k = len(idx)                # number of lpg_class rows for this egon_class
    base = n_class // k         # equal base allocation
    rest = n_class % k          # remaining profiles to distribute

    mapping.loc[idx, "n_profiles"] = base
    if rest:
        mapping.loc[idx[:rest], "n_profiles"] += 1

# Rows with egon_class == None/NaN remain at 0 automatically

# -----------------------
# 5) Save + checks
# -----------------------
mapping.to_csv(OUT_CSV, index=False)

print("✅ Written:", OUT_CSV)
print("Sum n_profiles:", int(mapping["n_profiles"].sum()))
print(
    "Classes with n_profiles > 0:",
    sorted(mapping.loc[mapping["n_profiles"] > 0, "egon_class"].dropna().unique())
)

print("\n--- n_profiles per egon_class (class totals) ---")
print(
    mapping.dropna(subset=["egon_class"])
    .groupby("egon_class")["n_profiles"]
    .sum()
    .sort_values(ascending=False)
)