#!/usr/bin/env python3
"""
Script to visualize accumulated daily profile for an entire profile type.
Aggregates all CSV files of a profile type (e.g., CHR01, CHR02) into one average daily profile.

Usage:
    python plot_profile_type.py CHR01      # Average of all CHR01 files
    python plot_profile_type.py CHR52      # Average of all CHR52 files
    python plot_profile_type.py --list     # Show available profile types
"""

import pandas as pd
import matplotlib.pyplot as plt
import argparse
import sys
import re
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / 'generated_profiles' / 'results'
PLOTS_DIR = Path(__file__).parent / 'generated_profiles' / 'plots'


def get_files_for_profile(profile_type: str) -> list[Path]:
    """Get all CSV files for a given profile type, sorted by name."""
    pattern = f"resulting_profiles_{profile_type}*_all.csv"
    files = sorted(RESULTS_DIR.glob(pattern))
    return files


def list_profiles():
    """List all available profile types and their file counts."""
    all_files = sorted(RESULTS_DIR.glob("resulting_profiles_CHR*.csv"))

    profiles = {}
    for f in all_files:
        match = re.search(r'resulting_profiles_(CHR\d+)', f.name)
        if match:
            profile_type = match.group(1)
            if profile_type not in profiles:
                profiles[profile_type] = []
            profiles[profile_type].append(f)

    print("Available profile types:")
    print("-" * 60)
    for profile_type in sorted(profiles.keys(), key=lambda x: int(x[3:])):
        count = len(profiles[profile_type])
        first_file = profiles[profile_type][0].name
        desc_match = re.search(r'resulting_profiles_CHR\d+\s*(.+?)_sfh_seed', first_file)
        desc = desc_match.group(1) if desc_match else ""
        print(f"  {profile_type:<6}  ({count:>2} files)  {desc}")


def get_profile_description(profile_type: str, files: list[Path]) -> str:
    """Extract profile description from filename."""
    if not files:
        return profile_type
    first_file = files[0].name
    desc_match = re.search(r'resulting_profiles_(CHR\d+\s*.+?)_sfh_seed', first_file)
    return desc_match.group(1) if desc_match else profile_type


def load_and_aggregate_all(files: list[Path]) -> pd.DataFrame:
    """Load all CSV files and aggregate into one daily profile."""
    all_data = []

    for filepath in files:
        df = pd.read_csv(filepath, index_col=0, parse_dates=True)
        df['time_of_day'] = df.index.time
        all_data.append(df)

    # Concatenate all dataframes
    combined = pd.concat(all_data, ignore_index=False)

    # Group by time of day and calculate mean across all days and all files
    daily_profile = combined.groupby('time_of_day').mean()

    return daily_profile


def plot_daily_profile(daily_profile: pd.DataFrame, title: str, num_files: int,
                       output_file: str, show: bool = False):
    """Plot the accumulated daily profile."""
    fig, ax = plt.subplots(figsize=(12, 6))

    # Convert time index to hours for better x-axis display
    times = daily_profile.index
    hours = [t.hour + t.minute / 60 for t in times]

    # Plot each column
    for col in daily_profile.columns:
        ax.plot(hours, daily_profile[col], label=col, linewidth=1.5)

    ax.set_xlabel('Time of Day (hours)', fontsize=12)
    ax.set_ylabel('Average Electricity Consumption (kW)', fontsize=12)
    ax.set_title(f'Accumulated Daily Profile (averaged over {num_files} files)\n{title}', fontsize=14)
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 2))
    ax.grid(True, alpha=0.3)
    ax.legend()

    plt.tight_layout()

    # Ensure output directory exists
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.savefig(output_file, dpi=150)
    print(f"Plot saved to: {output_file}")

    if show:
        plt.show()
    else:
        plt.close()


def main():
    parser = argparse.ArgumentParser(
        description='Plot accumulated daily profile for an entire profile type',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python plot_profile_type.py CHR01      # Average of all CHR01 files
    python plot_profile_type.py CHR52      # Average of all CHR52 files
    python plot_profile_type.py --list     # Show available profile types
        """
    )
    parser.add_argument(
        'profile_type',
        type=str,
        nargs='?',
        help='Profile type (e.g., CHR01, CHR52)'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output file path for saving the plot'
    )
    parser.add_argument(
        '--show',
        action='store_true',
        help='Show interactive plot window (blocks until closed)'
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available profile types'
    )

    args = parser.parse_args()

    if args.list:
        list_profiles()
        sys.exit(0)

    if not args.profile_type:
        parser.print_help()
        sys.exit(1)

    profile_type = args.profile_type.upper()
    files = get_files_for_profile(profile_type)

    if not files:
        print(f"Error: No files found for profile type: {profile_type}")
        print("Use --list to see available profile types.")
        sys.exit(1)

    print(f"Found {len(files)} files for {profile_type}")
    print("Loading and aggregating data...")

    daily_profile = load_and_aggregate_all(files)
    title = get_profile_description(profile_type, files)

    print(f"Data points per day: {len(daily_profile)}")

    # Default output filename
    output_file = args.output if args.output else str(PLOTS_DIR / f"{profile_type}_aggregated.png")

    plot_daily_profile(daily_profile, title, len(files), output_file, show=args.show)


if __name__ == '__main__':
    main()