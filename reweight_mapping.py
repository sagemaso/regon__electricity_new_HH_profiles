
"""
Reweight household profile counts (n_profiles) to match Census 2022 household distribution,
AND additionally reweight within each eGon hh_type by employment/work-pattern proxies derived
from Census 2000S-2005.

Inputs (defaults relative to this script):
  - mapping/Verteilung_hh_types_census22.ods     (sheet: n_profiles)
  - zensus/5000H-1006_de.csv                     (households by household type)
  - zensus/5000H-2001_de.csv                     (household size by household type)
  - zensus/6000F-2007_de.csv                     (household type × senior status; PO/PR split)
  - zensus/1000A-1035_de.csv                     (persons; "Singlehaushalte mit Senior/-in" for SO/SR)
  - zensus/2000S-2005_de.csv                     (persons by household type × employment status)

Output:
  - n_profiles_reweighted_999.csv

Main steps:
  1) Block targets from 5000H-1006
  2) P1/P2/P3 from 5000H-2001
  3) SR share from 1000A-1035 + singles total from 5000H-1006
  4) PR share from 6000F-2007
  5) Convert blocks -> eGon hh_types (SO, SR, PO, PR, P1..P3, SK, OO, OR)
  6) Within each eGon hh_type:
       allocate target counts across "work-pattern buckets" using Census 2000S-2005,
       then allocate within bucket across matching LPG classes.
     This fixes previously uniform/naive within-type distributions.

Work-pattern buckets:
  - Singles (SO): employed / unemployed / not_in_labor_force (students etc.)
  - Couples (PO, P1..P3): both_employed / one_employed / none_employed
  - Single parents (SK): employed / none_employed
  - Retired groups (SR, PR): forced none_employed (by definition)

Key assumption:
  - Seniors (SR) are largely not employed, so for SO shares we subtract SR from "not_in_labor_force".
    This is adjustable via --assume_sr_all_not_in_labor_force (default True).

Run:
  python reweight_mapping.py
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, Tuple, List

import numpy as np
import pandas as pd


# -----------------------------
# Helpers: strings, numbers, allocation
# -----------------------------

def normalize_label(x: str) -> str:
    s = str(x).replace("\u00a0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def to_int_de(series: pd.Series) -> pd.Series:
    s = series.astype(str)
    s = s.str.replace("\u00a0", "", regex=False)
    s = s.str.replace(" ", "", regex=False)
    s = s.str.replace(".", "", regex=False)
    s = s.str.strip()
    s = s.replace({"": "0", "nan": "0", "-": "0"})
    return s.astype(int)


def allocate_largest_remainder(weights: np.ndarray, total: int) -> np.ndarray:
    if total < 0:
        raise ValueError("total must be >= 0")
    if len(weights) == 0:
        return np.array([], dtype=int)

    w = np.array(weights, dtype=float)
    if np.all(w <= 0) or w.sum() <= 0:
        w = np.ones_like(w, dtype=float)

    raw = w / w.sum() * total
    flo = np.floor(raw).astype(int)

    remainder = int(total - flo.sum())
    frac = raw - flo
    order = np.argsort(-frac)

    for i in range(remainder):
        flo[order[i]] += 1
    return flo


def split_total_by_share(share_b: float, total: int) -> Tuple[int, int]:
    if not (0.0 <= share_b <= 1.0):
        raise ValueError("share_b must be in [0,1]")
    alloc = allocate_largest_remainder(np.array([1 - share_b, share_b], dtype=float), total)
    return int(alloc[0]), int(alloc[1])


def split_total_by_existing_ratio(existing_a: int, existing_b: int, total: int) -> Tuple[int, int]:
    if existing_a + existing_b == 0:
        a = total // 2
        b = total - a
        return a, b
    alloc = allocate_largest_remainder(np.array([existing_a, existing_b], dtype=float), total)
    return int(alloc[0]), int(alloc[1])


def read_zensus_semicolon_table(path: Path, skiprows: int) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    df = pd.read_csv(
        path,
        sep=";",
        skiprows=skiprows,
        header=None,
        dtype=str,
        encoding="utf-8-sig",
        engine="python",
    )
    if df.shape[0] > 0 and (df.iloc[:, 0] == "__________").any():
        cut = df.index[df.iloc[:, 0] == "__________"][0]
        df = df.iloc[:cut].copy()
    df = df.dropna(how="all")
    return df


# -----------------------------
# Zensus-derived shares: SR (singles), PR (couples w/o child)
# -----------------------------

def compute_pr_share_from_6000f_2007(path: Path) -> float:
    raw = read_zensus_semicolon_table(path, skiprows=6)
    raw = raw.iloc[:, :5].copy()
    raw.columns = ["date", "household_type", "senior_status", "count", "flag"]

    raw["household_type"] = raw["household_type"].map(normalize_label)
    raw["senior_status"] = raw["senior_status"].map(normalize_label)
    raw["count_i"] = to_int_de(raw["count"])

    ht = "Paare ohne Kind(er)"
    total = raw.loc[(raw["household_type"] == ht) & (raw["senior_status"] == "Insgesamt"), "count_i"]
    senior_only = raw.loc[
        (raw["household_type"] == ht) &
        (raw["senior_status"] == "Haushalte mit ausschließlich Senioren/-innen"),
        "count_i"
    ]
    if total.empty or senior_only.empty:
        raise ValueError("Required rows for PR share not found in 6000F-2007.")
    total_v = float(total.iloc[0])
    senior_only_v = float(senior_only.iloc[0])
    if total_v <= 0:
        raise ValueError("Total couples w/o children is <= 0.")
    return senior_only_v / total_v


def compute_sr_share_from_1000a_1035(path: Path, singles_total_from_5000h_1006: int) -> float:
    raw = read_zensus_semicolon_table(path, skiprows=6)
    raw = raw.iloc[:, :6].copy()
    raw.columns = ["date", "category", "count", "flag_count", "pct", "flag_pct"][: raw.shape[1]]

    raw["category"] = raw["category"].map(normalize_label)
    raw["count_i"] = to_int_de(raw["count"])

    num = raw.loc[raw["category"] == "Singlehaushalte mit Senior/-in", "count_i"]
    if num.empty:
        sample = raw["category"].dropna().unique().tolist()[:30]
        raise ValueError(
            "Could not find 'Singlehaushalte mit Senior/-in' in 1000A-1035 export. "
            f"Sample categories: {sample}"
        )

    single_seniors = int(num.iloc[0])
    if singles_total_from_5000h_1006 <= 0:
        raise ValueError("Singles total must be > 0.")
    return single_seniors / singles_total_from_5000h_1006


# -----------------------------
# Employment shares from 2000S-2005
# -----------------------------

def load_employment_shares_2000s_2005(path: Path) -> Dict[str, Dict[str, float]]:
    """
    Returns dict:
      employment_shares[household_type] = {
         'employed': ...,
         'unemployed': ...,
         'not_in_labor_force': ...,
         'under_min_age': ...
      }
    Derived from Zensus 2000S-2005 (persons by household type & employment status).
    """
    raw = read_zensus_semicolon_table(path, skiprows=6)

    # Layout usually:
    # col0=date, col1=household_type, col2=employment_status, col3=count, col4=flag
    if raw.shape[1] < 4:
        raise ValueError(f"Unexpected 2000S-2005 format: {raw.shape[1]} columns")

    raw = raw.iloc[:, :5].copy()
    raw.columns = ["date", "household_type", "employment_status", "count", "flag"][: raw.shape[1]]

    raw["household_type"] = raw["household_type"].map(normalize_label)
    raw["employment_status"] = raw["employment_status"].map(normalize_label)
    raw["count_i"] = to_int_de(raw["count"])

    # Normalize employment labels into our 4 buckets
    def norm_emp(s: str) -> str | None:
        s = normalize_label(s)
        if s == "Erwerbstätige":
            return "employed"
        if s == "Erwerbslose":
            return "unemployed"
        if s in ["Schüler/-innen u. Studierende (nicht erwerbsaktiv)", "Nichterwerbspersonen",
                 "Empfänger/-innen von Ruhegehalt/Kapitalerträgen", "Sonstige"]:
            return "not_in_labor_force"
        if s == "Personen unterhalb des Mindestalters":
            return "under_min_age"
        if s in ["Insgesamt", "Erwerbspersonen"]:
            return None
        return None

    raw["emp_norm"] = raw["employment_status"].map(norm_emp)
    raw = raw[raw["emp_norm"].notna()].copy()

    # total persons per household_type (from rows where employment_status == 'Insgesamt')
    totals = (
        read_zensus_semicolon_table(path, skiprows=6)
        .iloc[:, :5].copy()
    )
    totals.columns = ["date", "household_type", "employment_status", "count", "flag"][: totals.shape[1]]
    totals["household_type"] = totals["household_type"].map(normalize_label)
    totals["employment_status"] = totals["employment_status"].map(normalize_label)
    totals["count_i"] = to_int_de(totals["count"])
    totals = totals[totals["employment_status"] == "Insgesamt"].set_index("household_type")["count_i"].to_dict()

    out: Dict[str, Dict[str, float]] = {}
    for hh, sub in raw.groupby("household_type"):
        total = float(totals.get(hh, 0))
        if total <= 0:
            continue
        sums = sub.groupby("emp_norm")["count_i"].sum().to_dict()
        out[hh] = {
            "employed": float(sums.get("employed", 0.0)) / total * 100.0,
            "unemployed": float(sums.get("unemployed", 0.0)) / total * 100.0,
            "not_in_labor_force": float(sums.get("not_in_labor_force", 0.0)) / total * 100.0,
            "under_min_age": float(sums.get("under_min_age", 0.0)) / total * 100.0,
        }
    return out


# -----------------------------
# Profile -> work-pattern classification
# -----------------------------

def classify_profile_work_pattern(lpg_class: str, hh_type: str) -> str:
    """
    Classify a profile into a work-pattern bucket based on its text label.
    Buckets depend on household type.
    """
    s = lpg_class.lower()

    # Retired groups: force none employed
    if hh_type in ("SR", "PR"):
        return "none_employed"

    # Singles: employed / unemployed / not_in_labor_force
    if hh_type == "SO":
        if "jobless" in s or "unemploy" in s:
            return "unemployed"
        if "student" in s:
            return "not_in_labor_force"
        if "without work" in s or "no work" in s:
            return "not_in_labor_force"
        # shift worker or with work
        if "with work" in s or "shift" in s:
            return "employed"
        # fallback
        return "not_in_labor_force"

    # Single parent: employed / none
    if hh_type == "SK":
        if "with work" in s or "at work" in s or "employ" in s or "shift" in s:
            return "employed"
        if "without work" in s or "no work" in s:
            return "none_employed"
        return "none_employed"

    # Couples / families: both / one / none employed
    if hh_type in ("PO", "P1", "P2", "P3", "OR"):
        if "both at work" in s or "both with work" in s:
            return "both_employed"
        if "shiftworker couple" in s or ("shift" in s and "couple" in s):
            return "both_employed"
        if "one at work" in s or "man at work" in s or "dad employed" in s or "husband at work" in s or "1 at work" in s:
            return "one_employed"
        if "without work" in s or "no work" in s or "retired" in s:
            return "none_employed"
        # If unclear but mentions "with work" assume one employed
        if "with work" in s:
            return "one_employed"
        return "none_employed"

    # Other multi-person: keep simple
    if hh_type in ("OO",):
        if "student" in s:
            return "not_in_labor_force"
        return "not_in_labor_force"

    return "unknown"


# -----------------------------
# Allocate within hh_type using work-pattern targets
# -----------------------------

def allocate_within_type_by_buckets(
    sub_df: pd.DataFrame,
    target_total: int,
    bucket_shares: Dict[str, float],
    bucket_col: str = "bucket",
) -> np.ndarray:
    """
    Two-stage allocation:
      1) allocate target_total across buckets according to bucket_shares (largest remainder)
      2) within each bucket, allocate equally across rows (or by optional weights)

    Returns integer allocations per row in the same order as sub_df.
    """
    sub = sub_df.copy()
    sub[bucket_col] = sub[bucket_col].fillna("unknown")

    buckets = list(bucket_shares.keys())
    weights = np.array([max(bucket_shares[b], 0.0) for b in buckets], dtype=float)
    bucket_targets = allocate_largest_remainder(weights, target_total)
    bucket_targets = dict(zip(buckets, bucket_targets.tolist()))

    alloc = np.zeros(len(sub), dtype=int)

    for b in buckets:
        idx = sub.index[sub[bucket_col] == b].tolist()
        tgt = int(bucket_targets[b])
        if tgt <= 0:
            continue
        if len(idx) == 0:
            # No profiles for this bucket -> fallback distribute to all profiles
            idx = sub.index.tolist()
        # Equal weights inside bucket (because old weights were uniform/unrealistic)
        w = np.ones(len(idx), dtype=float)
        a = allocate_largest_remainder(w, tgt)
        alloc[sub.index.get_indexer(idx)] += a

    # If we have "unknown" rows and leftover issues, fix by final normalization
    diff = target_total - int(alloc.sum())
    if diff != 0:
        # add/remove to rows with largest/smallest current allocations
        order = np.argsort(-alloc) if diff > 0 else np.argsort(alloc)
        for i in range(abs(diff)):
            alloc[order[i % len(order)]] += 1 if diff > 0 else -1

    return alloc


# -----------------------------
# Main
# -----------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    script_dir = Path(__file__).resolve().parent

    parser.add_argument("--ods", type=Path, default=script_dir / "mapping" / "Verteilung_hh_types_census22.ods")
    parser.add_argument("--sheet", type=str, default="n_profiles")
    parser.add_argument("--c1006", type=Path, default=script_dir / "zensus" / "5000H-1006_de.csv")
    parser.add_argument("--c2001", type=Path, default=script_dir / "zensus" / "5000H-2001_de.csv")
    parser.add_argument("--c6000f", type=Path, default=script_dir / "zensus" / "6000F-2007_de.csv")
    parser.add_argument("--c1000a", type=Path, default=script_dir / "zensus" / "1000A-1035_de.csv")
    parser.add_argument("--c2000s", type=Path, default=script_dir / "zensus" / "2000S-2005_de.csv")
    parser.add_argument("--target-total", type=int, default=999)
    parser.add_argument("--out", type=Path, default=script_dir / "n_profiles_reweighted_999.csv")

    parser.add_argument(
        "--assume-sr-all-not-in-labor-force",
        action="store_true",
        default=True,
        help="Assume SR singles are 100% not_in_labor_force when deriving SO employment shares."
    )

    args = parser.parse_args()
    target_total = int(args.target_total)

    # Load ODS
    df = pd.read_excel(args.ods, sheet_name=args.sheet, engine="odf").copy()
    df = df[df["lpg class"] != "lpg_class"].copy()
    df["lpg_class"] = df["lpg class"].astype(str)
    df["hh_type"] = df["HH type eGon"].astype(str).map(normalize_label)
    n_col = "Anazhl verschiedener Profile (siehe anteile_lt_zensus)"
    df["n_profiles"] = pd.to_numeric(df[n_col], errors="coerce").fillna(0).astype(int)

    print("Loaded ODS rows:", len(df))
    print("Current sum n_profiles:", int(df["n_profiles"].sum()))

    # Existing ratio for OO/OR fallback
    cur_by_type = df.groupby("hh_type")["n_profiles"].sum().to_dict()
    def cur(t: str) -> int:
        return int(cur_by_type.get(t, 0))

    # Load 5000H-1006 block totals
    c1006 = read_zensus_semicolon_table(args.c1006, skiprows=6)
    c1006 = c1006.iloc[:, :6].copy()
    c1006.columns = ["date", "household_type", "count", "flag_count", "pct", "flag_pct"][: c1006.shape[1]]
    c1006["household_type"] = c1006["household_type"].map(normalize_label)
    c1006["count_i"] = to_int_de(c1006["count"])

    CENSUS_BLOCK_MAP = {
        "Einpersonenhaushalte (Singlehaushalte)": "SINGLE",
        "Paare ohne Kind(er)": "COUPLE_NO_CHILD",
        "Paare mit Kind(ern)": "COUPLE_CHILD",
        "Alleinerziehende Elternteile": "SINGLE_PARENT",
        "Mehrpersonenhaushalte ohne Kernfamilie": "OTHER_MULTI",
    }

    c1006_use = c1006[c1006["household_type"] != "Insgesamt"].copy()
    c1006_use["block"] = c1006_use["household_type"].map(CENSUS_BLOCK_MAP)
    block_counts = c1006_use.groupby("block")["count_i"].sum()
    block_shares = block_counts / block_counts.sum()

    block_targets_vec = allocate_largest_remainder(block_shares.to_numpy(dtype=float), target_total)
    block_targets = dict(zip(block_shares.index.tolist(), block_targets_vec.tolist()))

    print(f"\nTarget blocks for {target_total} profiles (from Census 5000H-1006):")
    for k, v in sorted(block_targets.items()):
        print(f"  {k:15s}: {v}")

    singles_total_zensus = int(c1006.loc[
        c1006["household_type"] == "Einpersonenhaushalte (Singlehaushalte)", "count_i"
    ].iloc[0])

    # P1/P2/P3 split from 5000H-2001
    c2001 = read_zensus_semicolon_table(args.c2001, skiprows=6)
    c2001 = c2001.iloc[:, :5].copy()
    c2001.columns = ["date", "hh_size", "household_type", "count", "flag"][: c2001.shape[1]]
    c2001["household_type"] = c2001["household_type"].map(normalize_label)
    c2001["hh_size"] = c2001["hh_size"].map(normalize_label)
    c2001["count_i"] = to_int_de(c2001["count"])

    cc = c2001[c2001["household_type"] == "Paare mit Kind(ern)"].copy()
    cc_total = int(cc.loc[cc["hh_size"] == "Insgesamt", "count_i"].iloc[0])
    cc_sizes = cc[cc["hh_size"] != "Insgesamt"].copy()

    def size_label_to_n(label: str) -> int:
        if label.startswith("6"):
            return 6
        m = re.match(r"(\d+)", label)
        if not m:
            raise ValueError(f"Cannot parse hh_size label: {label}")
        return int(m.group(1))

    cc_sizes["n"] = cc_sizes["hh_size"].map(size_label_to_n)
    cc_sizes["p_size"] = cc_sizes["count_i"] / cc_total

    p1_share = float(cc_sizes.loc[cc_sizes["n"] == 3, "p_size"].sum())
    p2_share = float(cc_sizes.loc[cc_sizes["n"] == 4, "p_size"].sum())
    p3_share = float(cc_sizes.loc[cc_sizes["n"] >= 5, "p_size"].sum())

    p123 = np.array([p1_share, p2_share, p3_share], dtype=float)
    p123 = p123 / p123.sum()

    couple_child_total = int(block_targets["COUPLE_CHILD"])
    P1_T, P2_T, P3_T = map(int, allocate_largest_remainder(p123, couple_child_total).tolist())

    print("\nSplit COUPLE_CHILD into P1/P2/P3 from 5000H-2001:")
    print(f"  P1: {P1_T}, P2: {P2_T}, P3: {P3_T}")

    # PR + SR shares
    pr_share = compute_pr_share_from_6000f_2007(args.c6000f)
    sr_share = compute_sr_share_from_1000a_1035(args.c1000a, singles_total_zensus)
    print(f"\nComputed PR share: {pr_share:.6f} ({pr_share*100:.2f}%)")
    print(f"Computed SR share: {sr_share:.6f} ({sr_share*100:.2f}%)")

    # Split blocks into eGon types
    SINGLE_T = int(block_targets["SINGLE"])
    SO_T, SR_T = split_total_by_share(sr_share, SINGLE_T)

    CNC_T = int(block_targets["COUPLE_NO_CHILD"])
    PO_T, PR_T = split_total_by_share(pr_share, CNC_T)

    SK_T = int(block_targets["SINGLE_PARENT"])
    OM_T = int(block_targets["OTHER_MULTI"])
    OO_T, OR_T = split_total_by_existing_ratio(cur("OO"), cur("OR"), OM_T)

    target_totals = {
        "SO": SO_T, "SR": SR_T,
        "PO": PO_T, "PR": PR_T,
        "P1": P1_T, "P2": P2_T, "P3": P3_T,
        "SK": SK_T,
        "OO": OO_T, "OR": OR_T
    }

    print("\nFinal target totals by eGon hh_type:")
    print("  Sum targets:", sum(target_totals.values()))
    for k in ["SO","SR","PO","PR","P1","P2","P3","SK","OO","OR"]:
        print(f"  {k}: {target_totals[k]}")

    # Load employment shares from 2000S-2005
    emp_shares = load_employment_shares_2000s_2005(args.c2000s)

    # Helper to get census employment shares for the matching Zensus household type
    def get_emp(hh_label: str) -> Dict[str, float]:
        if hh_label not in emp_shares:
            raise ValueError(f"Employment shares missing for household type: {hh_label}")
        return emp_shares[hh_label]

    # Map from our eGon types to the Zensus household type label used in 2000S-2005
    EGON_TO_ZENSUS_EMP = {
        "SO": "Einpersonenhaushalte (Singlehaushalte)",
        "SR": "Einpersonenhaushalte (Singlehaushalte)",
        "PO": "Paare ohne Kind(er)",
        "PR": "Paare ohne Kind(er)",
        "P1": "Paare mit Kind(ern)",
        "P2": "Paare mit Kind(ern)",
        "P3": "Paare mit Kind(ern)",
        "SK": "Alleinerziehende Elternteile",
        "OO": "Mehrpersonenhaushalte ohne Kernfamilie",
        "OR": "Mehrpersonenhaushalte ohne Kernfamilie",
    }

    # Derive within-type bucket shares from census employment shares
    def bucket_shares_for_type(e_type: str) -> Dict[str, float]:
        # Retired types: fixed none employed
        if e_type in ("SR", "PR"):
            return {"none_employed": 1.0}

        z = get_emp(EGON_TO_ZENSUS_EMP[e_type])  # percentages (0..100)

        # Singles SO: adjust by subtracting SR from not_in_labor_force if requested
        if e_type == "SO":
            employed = z["employed"] / 100.0
            unemployed = z["unemployed"] / 100.0
            nilf = z["not_in_labor_force"] / 100.0

            # Adjustment: remove seniors (SR share) from nilf to approximate SO composition
            if args.assume_sr_all_not_in_labor_force:
                nilf_adj = max(0.0, nilf - sr_share)
                denom = max(1e-12, 1.0 - sr_share)
                employed = employed / denom
                unemployed = unemployed / denom
                nilf = nilf_adj / denom

            # normalize (guard numerical drift)
            total = employed + unemployed + nilf
            if total <= 0:
                return {"employed": 0.5, "unemployed": 0.05, "not_in_labor_force": 0.45}
            return {
                "employed": employed / total,
                "unemployed": unemployed / total,
                "not_in_labor_force": nilf / total,
            }

        # Single parent: bucket to employed vs none (unemployed + nilf)
        if e_type == "SK":
            employed = z["employed"] / 100.0
            none = (z["unemployed"] + z["not_in_labor_force"]) / 100.0
            total = employed + none
            return {"employed": employed / total, "none_employed": none / total}

        # Couples/families: convert person-level employed share into a proxy for adults
        # We approximate p = employed / (1 - under_min_age) as "employment probability among eligible persons".
        # Then use binomial for 2 adults: both/one/none.
        if e_type in ("PO", "P1", "P2", "P3", "OR"):
            eligible = max(1e-12, 1.0 - z["under_min_age"] / 100.0)
            p = (z["employed"] / 100.0) / eligible
            p = min(max(p, 0.0), 1.0)

            both = p * p
            one = 2 * p * (1 - p)
            none = (1 - p) * (1 - p)
            total = both + one + none
            return {"both_employed": both / total, "one_employed": one / total, "none_employed": none / total}

        # OO: keep simple (often student-like)
        if e_type == "OO":
            # not enough structure -> keep not_in_labor_force
            return {"not_in_labor_force": 1.0}

        return {"unknown": 1.0}

    # Classify each row into a bucket
    df["bucket"] = df.apply(lambda r: classify_profile_work_pattern(r["lpg_class"], r["hh_type"]), axis=1)

    # Allocate within each hh_type using bucket shares
    df["n_profiles_new"] = 0

    for hh_type, tgt in target_totals.items():
        mask = df["hh_type"] == hh_type
        sub = df.loc[mask].copy()
        if sub.empty:
            print(f"WARNING: No rows for hh_type={hh_type}, target={tgt}")
            continue

        shares = bucket_shares_for_type(hh_type)
        alloc = allocate_within_type_by_buckets(sub, int(tgt), shares, bucket_col="bucket")
        df.loc[mask, "n_profiles_new"] = alloc

    # Validation
    print("\nValidation:")
    print("  Sum old:", int(df["n_profiles"].sum()))
    print("  Sum new:", int(df["n_profiles_new"].sum()))
    print("\nBy hh_type (old vs new):")
    print(df.groupby("hh_type")[["n_profiles", "n_profiles_new"]].sum().sort_index())

    out = df[["lpg_class", "hh_type", "n_profiles", "n_profiles_new"]].copy()
    out.to_csv(args.out, index=False)
    print("\nWrote:", args.out)


if __name__ == "__main__":
    main()