# Household Electricity Profile Generator

Generate synthetic household electricity load profiles for Germany, weighted to match Census (Zensus) 2022 distribution.

## Overview

This project creates realistic 15-minute resolution electricity consumption profiles for different household types using the Load Profile Generator (LPG) library. The goal is to produce ~999 representative profiles that, when aggregated, reflect the actual composition of German households.

---

## Census Tables (Zensus 2022)

The profile counts in `n_profiles_reweighted_999.csv` are derived from these tables (processed by `reweight_mapping.py`):

| Table | Content |
|-------|---------|
| `5000H-1006_de.csv` | Household counts by type (singles, couples, families). Used to determine how many of each household type. |
| `5000H-2001_de.csv` | Household size distribution (1-6+ persons). Used to split families into P1/P2/P3 (1/2/3+ kids). |
| `6000F-2007_de.csv` | Couples by senior status (retired vs. working-age). Used to split couples into PR (retired) vs PO. |
| `1000A-1035_de.csv` | Single households with seniors. Used to split singles into SR (retired) vs SO. |
| `2000S-2005_de.csv` | Employment status by household type. Used to weight profiles by work patterns (both employed, one employed, none employed, etc.). |

---

## Household Types (eGon Classification)

| Code | Description |
|------|-------------|
| SO | Single, Other (working-age single without children) |
| SR | Single, Retired (senior living alone) |
| PO | Pair, Other (couple without children, working-age) |
| PR | Pair, Retired (couple without children, both seniors) |
| P1 | Pair + 1 child |
| P2 | Pair + 2 children |
| P3 | Pair + 3 or more children |
| SK | Single parent with child(ren) (Alleinerziehend mit Kind) |
| OO | Other, Other (multi-person household, no nuclear family, working) |
| OR | Other, Retired (multi-person household, no nuclear family, seniors) |

---

## Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Census Data (zensus/*.csv)                                                 │
│  - Household type distribution                                              │
│  - Employment rates                                                         │
│  - Senior status                                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  reweight_mapping.py                                                        │
│  - Calculates how many profiles to generate per LPG household class        │
│  - Weights by census household distribution                                 │
│  - Weights by employment patterns within each household type                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  n_profiles_reweighted_999.csv                                              │
│  - Target count for each LPG household class                                │
│  - Example: "CHR01 Couple both at Work" → 15 profiles                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  create_profiles_census_2022_de.py                                          │
│  - Reads target counts                                                      │
│  - Calls LPG for each household type                                        │
│  - Generates SFH and MFH variants                                           │
│  - Saves 15-minute resolution profiles                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  generated_profiles/results/                                                │
│  - ~999 CSV files (one per profile)                                         │
│  - 35,040 rows each (365 days × 96 quarter-hours)                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Input Files

### n_profiles_reweighted_999.csv

Contains the target number of profiles to generate for each LPG household class.

| Column | Description |
|--------|-------------|
| `lpg_class` | LPG household type name (e.g., "CHR01 Couple both at Work") |
| `hh_type` | eGon household category (SO, SR, PO, PR, P1, P2, P3, SK, OO, OR) |
| `n_profiles` | Original count (before reweighting) |
| `n_profiles_new` | Census-weighted count (this is what we use) |

---

## Output Files

### generated_profiles/new_results/

One CSV file per generated profile:

```
resulting_profiles_{household_name}_{house_type}_seed_{random_seed}.csv
```

Each file contains:
- **Index:** Timestamp (15-minute intervals for full year 2022)
- **Column:** `Electricity_HH1` (electricity consumption in kW)
- **Rows:** 35,040 (= 365 days × 96 quarter-hours)

---

## Reweighting Algorithm (reweight_mapping.py)

This section explains how `n_profiles_reweighted_999.csv` is calculated from Census data.

### Goal

Distribute 999 profiles across ~65 LPG household classes so that:
1. The household type distribution matches Census 2022
2. Within each type, employment patterns match Census employment data

### Step 1: Block-Level Allocation

First, the 999 profiles are distributed across 5 major household "blocks" based on Census table `5000H-1006_de.csv`:

```
Census 5000H-1006 contains:
┌─────────────────────────────────────┬─────────────┬─────────┐
│ Household Type (German)             │ Block Name  │ Count   │
├─────────────────────────────────────┼─────────────┼─────────┤
│ Einpersonenhaushalte (Singlehaus.)  │ SINGLE      │ ~17.8M  │
│ Paare ohne Kind(er)                 │ COUPLE_NO_  │ ~10.5M  │
│ Paare mit Kind(ern)                 │ COUPLE_     │ ~5.8M   │
│ Alleinerziehende Elternteile        │ SINGLE_     │ ~1.6M   │
│ Mehrpersonenhaushalte ohne Kernfam. │ OTHER_MULTI │ ~1.2M   │
└─────────────────────────────────────┴─────────────┴─────────┘
```

**Calculation:**
```
block_share = block_count / total_households
block_target = round(block_share × 999)
```

Using the **Largest Remainder Method** to ensure integer allocation sums to exactly 999.

### Step 2: Split Singles into SO/SR

The SINGLE block must be split into:
- **SO** (Single, Other): working-age singles
- **SR** (Single, Retired): senior singles

**Data source:** `1000A-1035_de.csv` contains "Singlehaushalte mit Senior/-in"

**Calculation:**
```
sr_share = senior_singles / total_singles
SR_target = round(sr_share × SINGLE_target)
SO_target = SINGLE_target - SR_target
```

### Step 3: Split Couples without Children into PO/PR

The COUPLE_NO_CHILD block must be split into:
- **PO** (Pair, Other): working-age couples
- **PR** (Pair, Retired): retired couples

**Data source:** `6000F-2007_de.csv` contains couples by senior status

**Calculation:**
```
pr_share = couples_with_exclusively_seniors / total_couples_no_child
PR_target = round(pr_share × COUPLE_NO_CHILD_target)
PO_target = COUPLE_NO_CHILD_target - PR_target
```

### Step 4: Split Families into P1/P2/P3

The COUPLE_CHILD block must be split by number of children:
- **P1**: 1 child (household size = 3)
- **P2**: 2 children (household size = 4)
- **P3**: 3+ children (household size = 5+)

**Data source:** `5000H-2001_de.csv` contains household size distribution

**Calculation:**
```
For "Paare mit Kind(ern)":
  p1_share = households_size_3 / total_couple_child
  p2_share = households_size_4 / total_couple_child
  p3_share = households_size_5+ / total_couple_child

P1_target = round(p1_share × COUPLE_CHILD_target)
P2_target = round(p2_share × COUPLE_CHILD_target)
P3_target = round(p3_share × COUPLE_CHILD_target)
```

### Step 5: Other Types

- **SK** (Single Parent): Takes the full SINGLE_PARENT block target
- **OO/OR** (Other): Split equally

### Step 6: Employment-Based Allocation Within Types

Now each eGon type (SO, SR, PO, PR, P1, P2, P3, SK, OO, OR) has a target count.
But each type contains multiple LPG classes with different work patterns.

**Example:** Type "PO" (working-age couples) includes:
- "CHR01 Couple both at Work"
- "CHR02 Couple, 1 at Work"
- "CHR03 Couple, Unemployed"

The allocation within each type uses Census employment data (`2000S-2005_de.csv`).

#### Work-Pattern Buckets

Each LPG class is classified into a bucket based on its name:

| Household Type | Buckets |
|----------------|---------|
| SO (singles) | employed, unemployed, not_in_labor_force |
| SR (retired singles) | none_employed (fixed) |
| PO, P1, P2, P3 (couples/families) | both_employed, one_employed, none_employed |
| PR (retired couples) | none_employed (fixed) |
| SK (single parents) | employed, none_employed |
| OO (other working) | not_in_labor_force |
| OR (other retired) | none_employed |

#### Bucket Share Calculation

**For Singles (SO):**
```
From Census 2000S-2005:
  employed_share = Erwerbstätige / Total
  unemployed_share = Erwerbslose / Total
  nilf_share = (Nichterwerbspersonen + Studierende + ...) / Total

Adjustment: Subtract SR (seniors) from not_in_labor_force
  (because seniors are mostly not employed, and we already separated them)
```

**For Couples (PO, P1, P2, P3):**

Census gives person-level employment rates, but we need household-level (both/one/none).

**Assumption:** Two adults with independent employment probability `p`:
```
p = employed_persons / eligible_persons  (excluding children)

Using binomial distribution for 2 adults:
  both_employed = p²
  one_employed = 2 × p × (1-p)
  none_employed = (1-p)²
```

#### Final Allocation

Within each bucket, profiles are distributed equally across matching LPG classes:

```
For each eGon type:
  1. Calculate bucket_target = type_target × bucket_share
  2. Find all LPG classes matching this bucket
  3. Distribute bucket_target equally across these classes
```

### Example Walkthrough

**Target:** 999 profiles total

**Step 1 - Blocks:**
```
SINGLE:       416 profiles (41.6%)
COUPLE_NO_CHILD: 247 profiles (24.7%)
COUPLE_CHILD: 137 profiles (13.7%)
SINGLE_PARENT: 38 profiles (3.8%)
OTHER_MULTI:  161 profiles (16.1%)
```

**Step 2 - Split Singles:**
```
SR share = 38% (from 1000A-1035)
SR = 158, SO = 258
```

**Step 3 - Split Couples:**
```
PR share = 45% (from 6000F-2007)
PR = 111, PO = 136
```

**Step 4 - Split Families:**
```
P1 = 65, P2 = 52, P3 = 20
```

**Step 6 - Within PO (136 profiles):**
```
Employment probability p = 0.75
  both_employed: 56% → 76 profiles
  one_employed:  38% → 52 profiles
  none_employed:  6% →  8 profiles

If "both_employed" bucket has 3 LPG classes:
  Each gets 76/3 ≈ 25 profiles
```

---

## Profile Generation (create_profiles_census_2022_de.py)

### 1. Load Mapping

Read `n_profiles_reweighted_999.csv` to get the target count for each household type.

### 2. For Each Household Type with n_profiles > 0

#### a) Generate N profiles for Single-Family House (SFH)
- Call LPG with `HT20_Single_Family_House_no_heating_cooling`
- Each profile uses a different random seed for variation
- LPG simulates daily routines: waking, cooking, TV, laundry, etc.
- Output: 1-hour resolution electricity data

#### b) Generate N profiles for Multi-Family House (MFH)
- Call LPG with `HT22_Big_Multifamily_House_no_heating_cooling`
- Same household behavior, but different house characteristics

### 3. Resample to 15-Minute Resolution

The LPG outputs 1-hour data, which is resampled to 15-minute intervals.

### 4. Save Each Profile Immediately

Each profile is saved right after generation to prevent data loss on crash.

---

## House Types

| Type | LPG Constant | Description |
|------|--------------|-------------|
| SFH | `HT20_Single_Family_House_no_heating_cooling` | Detached house |
| MFH | `HT22_Big_Multifamily_House_no_heating_cooling` | Apartment building |

**Note:** "no_heating_cooling" means only electricity for appliances/lighting is simulated, not space heating or cooling (which depends on building physics).

---

## Usage

```bash
python create_profiles_census_2022_de.py
```

This runs the main `run()` function, which generates all profiles.

---

## File Structure

```
new_HH_profiles/
├── create_profiles_census_2022_de.py   # Main profile generation script
├── reweight_mapping.py                 # Census weighting calculations
├── n_profiles_reweighted_999.csv       # Target profile counts (output of reweight_mapping.py)
├── mapping/
│   ├── household_type_matching_census22.csv   # LPG → eGon mapping
│   ├── hh_counts_de.csv                       # Household counts by eGon class
│   └── Verteilung_hh_types_census22.ods       # Distribution workbook
├── zensus/
│   ├── 5000H-1006_de.csv   # Households by type
│   ├── 5000H-2001_de.csv   # Household size distribution
│   ├── 6000F-2007_de.csv   # Senior status (couples)
│   ├── 1000A-1035_de.csv   # Senior status (singles)
│   ├── 2000S-2005_de.csv   # Employment status
│   ├── census_io.py        # CSV reader utility
│   ├── text_utils.py       # Label normalization
│   └── german_number_utils.py  # German number parsing
└── generated_profiles/
    └── results/            # Output: ~999 CSV profile files
```