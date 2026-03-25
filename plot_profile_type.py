#!/usr/bin/env python3
"""
Script to visualize accumulated daily profile from CSV files in a folder.

Usage:
    python plot_profile_type.py /path/to/folder/with/csvs
"""

import pandas as pd
import matplotlib.pyplot as plt
import argparse
import re
from pathlib import Path
from datetime import datetime


def plot_profiles(input_dir: str):
    """
    Load all CSV files from input_dir, aggregate into daily profiles, and save plots.

    Args:
        input_dir: Absolute path to folder containing CSV files
    """
    input_path = Path(input_dir)

    if not input_path.exists():
        print(f"Error: Directory does not exist: {input_dir}")
        return

    # Create output directory: input_dir_name + plots_ + date
    date_str = datetime.now().strftime("%Y%m%d")
    output_dir = input_path.parent / f"plots_{input_path.name}_{date_str}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all CSV files
    all_files = sorted(input_path.glob("*.csv"))

    if not all_files:
        print(f"Error: No CSV files found in {input_dir}")
        return

    print(f"Found {len(all_files)} CSV files in {input_dir}")
    print(f"Output directory: {output_dir}")

    # Group files by profile type (CHR##)
    profiles = {}
    for f in all_files:
        match = re.search(r'(CHR\d+)', f.name)
        if match:
            profile_type = match.group(1)
            if profile_type not in profiles:
                profiles[profile_type] = []
            profiles[profile_type].append(f)

    if not profiles:
        print("No CHR## profile types found in filenames. Processing all files together.")
        daily_profile_mean = load_and_aggregate(all_files, agg_func='mean')
        output_file = output_dir / "all_profiles_average.png"
        plot_daily_profile(daily_profile_mean, "All Profiles", len(all_files), output_file, agg_type='mean')

        daily_profile_sum = load_and_aggregate(all_files, agg_func='sum')
        output_file = output_dir / "all_profiles_accumulated.png"
        plot_daily_profile(daily_profile_sum, "All Profiles", len(all_files), output_file, agg_type='sum')
        return

    print(f"Found {len(profiles)} profile types: {', '.join(sorted(profiles.keys()))}")

    # Process each profile type
    for profile_type in sorted(profiles.keys(), key=lambda x: int(x[3:])):
        files = profiles[profile_type]
        title = get_profile_description(profile_type, files)
        print(f"\nProcessing {profile_type} ({len(files)} files)...")

        # Average plot
        daily_profile_mean = load_and_aggregate(files, agg_func='mean')
        output_file = output_dir / f"{profile_type}_average.png"
        plot_daily_profile(daily_profile_mean, title, len(files), output_file, agg_type='mean')

        # Summed plot
        daily_profile_sum = load_and_aggregate(files, agg_func='sum')
        output_file = output_dir / f"{profile_type}_accumulated.png"
        plot_daily_profile(daily_profile_sum, title, len(files), output_file, agg_type='sum')

    # Also create combined plots for all files
    print(f"\nCreating combined plots for all {len(all_files)} files...")

    daily_profile_mean = load_and_aggregate(all_files, agg_func='mean')
    output_file = output_dir / "all_profiles_average.png"
    plot_daily_profile(daily_profile_mean, "All Profile Types", len(all_files), output_file, agg_type='mean')

    daily_profile_sum = load_and_aggregate(all_files, agg_func='sum')
    output_file = output_dir / "all_profiles_accumulated.png"
    plot_daily_profile(daily_profile_sum, "All Profile Types", len(all_files), output_file, agg_type='sum')

    # Create seasonal plots (winter and summer)
    for season in ['winter', 'summer']:
        print(f"\nCreating {season} plots for all {len(all_files)} files...")

        daily_profile_mean = load_and_aggregate(all_files, agg_func='mean', season=season)
        output_file = output_dir / f"all_profiles_average_{season}.png"
        plot_daily_profile(daily_profile_mean, "All Profile Types", len(all_files), output_file, agg_type='mean', season=season)

        daily_profile_sum = load_and_aggregate(all_files, agg_func='sum', season=season)
        output_file = output_dir / f"all_profiles_accumulated_{season}.png"
        plot_daily_profile(daily_profile_sum, "All Profile Types", len(all_files), output_file, agg_type='sum', season=season)

    print(f"\nDone! All plots saved to: {output_dir}")


def get_profile_description(profile_type: str, files: list[Path]) -> str:
    """Extract profile description from filename."""
    if not files:
        return profile_type
    first_file = files[0].name
    # Try different filename patterns
    for pattern in [r'(CHR\d+\s*.+?)_sfh_seed', r'(CHR\d+\s*.+?)_seed', r'(CHR\d+[^_]*)']:
        match = re.search(pattern, first_file)
        if match:
            return match.group(1)
    return profile_type


def load_and_aggregate(files: list[Path], agg_func: str = 'mean', season: str = None) -> pd.DataFrame:
    """Load all CSV files and aggregate into one daily profile.

    Args:
        files: List of CSV file paths
        agg_func: Aggregation function - 'mean' for average, 'sum' for accumulated
        season: Optional season filter - 'winter' (Dec, Jan, Feb) or 'summer' (Jun, Jul, Aug)
    """
    all_data = []

    for i, filepath in enumerate(files):
        if len(files) > 20 and (i + 1) % 10 == 0:
            print(f"  Loaded {i + 1}/{len(files)} files...")
        df = pd.read_csv(filepath, index_col=0, parse_dates=True)
        df['time_of_day'] = df.index.time
        all_data.append(df)

    combined = pd.concat(all_data, ignore_index=False)

    # Filter by season if specified
    if season == 'winter':
        combined = combined[combined.index.month.isin([12, 1, 2])]
    elif season == 'summer':
        combined = combined[combined.index.month.isin([6, 7, 8])]

    if agg_func == 'sum':
        daily_profile = combined.groupby('time_of_day').sum()
    else:
        daily_profile = combined.groupby('time_of_day').mean()

    return daily_profile


def plot_daily_profile(daily_profile: pd.DataFrame, title: str, num_files: int,
                       output_file: Path, agg_type: str = 'mean', season: str = None):
    """Plot the daily profile.

    Args:
        agg_type: 'mean' for averaged plot, 'sum' for accumulated plot
        season: Optional season label for the title
    """
    plt.close('all')
    fig, ax = plt.subplots(figsize=(12, 6))

    times = daily_profile.index
    hours = [t.hour + t.minute / 60 for t in times]

    for col in daily_profile.columns:
        ax.plot(hours, daily_profile[col], label=col, linewidth=1.5)

    ax.set_xlabel('Time of Day (hours)', fontsize=12)

    season_str = f" - {season.capitalize()}" if season else ""
    if agg_type == 'sum':
        ax.set_ylabel('Total Electricity Consumption (kWh)', fontsize=12)
        ax.set_title(f'Accumulated Daily Profile{season_str} (summed over {num_files} files)\n{title}', fontsize=14)
    else:
        ax.set_ylabel('Average Electricity Consumption (kW)', fontsize=12)
        ax.set_title(f'Daily Profile{season_str} (averaged over {num_files} files)\n{title}', fontsize=14)

    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 2))
    ax.grid(True, alpha=0.3)
    ax.legend()

    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    print(f"  Saved: {output_file.name}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(
        description='Plot accumulated daily profiles from CSV files in a folder'
    )
    parser.add_argument(
        'input_dir',
        type=str,
        help='Absolute path to folder containing CSV files'
    )

    args = parser.parse_args()
    plot_profiles(args.input_dir)


if __name__ == '__main__':
    main()