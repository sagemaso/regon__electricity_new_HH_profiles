#!/usr/bin/env python3
"""
Script to visualize accumulated daily profile from electricity consumption data.
Aggregates values at each time point across all days of the year and plots the average.

Usage:
    python plot_daily_profile.py CHR01-1      # First file of CHR01 profile
    python plot_daily_profile.py CHR52-10     # 10th file of CHR52 profile
    python plot_daily_profile.py --list       # Show available profiles
"""

import pandas as pd
import matplotlib.pyplot as plt
import argparse
import sys
import re
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / 'generated_profiles' / 'results'


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
        # Extract profile type (e.g., "CHR01", "CHR52")
        match = re.search(r'resulting_profiles_(CHR\d+)', f.name)
        if match:
            profile_type = match.group(1)
            if profile_type not in profiles:
                profiles[profile_type] = []
            profiles[profile_type].append(f)

    print("Available profiles:")
    print("-" * 50)
    for profile_type in sorted(profiles.keys(), key=lambda x: int(x[3:])):
        count = len(profiles[profile_type])
        # Get the description from first filename
        first_file = profiles[profile_type][0].name
        desc_match = re.search(r'resulting_profiles_CHR\d+\s*(.+?)_sfh_seed', first_file)
        desc = desc_match.group(1) if desc_match else ""
        print(f"  {profile_type}-1 to {profile_type}-{count:<3}  ({count:>2} files)  {desc}")


def resolve_profile_id(profile_id: str) -> Path:
    """Resolve a profile ID like 'CHR01-1' to a file path."""
    match = re.match(r'(CHR\d+)-(\d+)', profile_id, re.IGNORECASE)
    if not match:
        print(f"Error: Invalid profile ID format: {profile_id}")
        print("Expected format: CHR01-1, CHR52-10, etc.")
        sys.exit(1)

    profile_type = match.group(1).upper()
    index = int(match.group(2))

    files = get_files_for_profile(profile_type)

    if not files:
        print(f"Error: No files found for profile type: {profile_type}")
        print("Use --list to see available profiles.")
        sys.exit(1)

    if index < 1 or index > len(files):
        print(f"Error: Index {index} out of range for {profile_type} (1-{len(files)} available)")
        sys.exit(1)

    return files[index - 1]  # Convert to 0-based index


def load_and_process_data(filepath: Path) -> pd.DataFrame:
    """Load CSV and process into daily profile."""
    df = pd.read_csv(filepath, index_col=0, parse_dates=True)

    # Extract time of day from index
    df['time_of_day'] = df.index.time

    # Group by time of day and calculate mean across all days
    daily_profile = df.groupby('time_of_day').mean()

    return daily_profile


def plot_daily_profile(daily_profile: pd.DataFrame, title: str, output_file: str, show: bool = False):
    """Plot the accumulated daily profile."""
    fig, ax = plt.subplots(figsize=(12, 6))

    # Convert time index to hours for better x-axis display
    times = daily_profile.index
    hours = [t.hour + t.minute / 60 for t in times]

    # Plot each column (in case there are multiple)
    for col in daily_profile.columns:
        ax.plot(hours, daily_profile[col], label=col, linewidth=1.5)

    ax.set_xlabel('Time of Day (hours)', fontsize=12)
    ax.set_ylabel('Average Electricity Consumption (kW)', fontsize=12)
    ax.set_title(f'Accumulated Daily Profile\n{title}', fontsize=14)
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 2))
    ax.grid(True, alpha=0.3)
    ax.legend()

    plt.tight_layout()

    plt.savefig(output_file, dpi=150)
    print(f"Plot saved to: {output_file}")

    if show:
        plt.show()
    else:
        plt.close()


def main():
    parser = argparse.ArgumentParser(
        description='Plot accumulated daily profile from electricity consumption data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python plot_daily_profile.py CHR01-1      # First file of CHR01 profile
    python plot_daily_profile.py CHR52-10     # 10th file of CHR52 profile
    python plot_daily_profile.py --list       # Show available profiles
        """
    )
    parser.add_argument(
        'profile_id',
        type=str,
        nargs='?',
        help='Profile ID in format CHR01-1, CHR52-10, etc.'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output file path for saving the plot (default: <profile_id>.png)'
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

    if not args.profile_id:
        parser.print_help()
        sys.exit(1)

    filepath = resolve_profile_id(args.profile_id)

    print(f"Loading data from: {filepath.name}")
    daily_profile = load_and_process_data(filepath)

    print(f"Data points per day: {len(daily_profile)}")

    # Extract profile description for title
    desc_match = re.search(r'resulting_profiles_(CHR\d+\s*.+?)_sfh_seed', filepath.name)
    title = desc_match.group(1) if desc_match else args.profile_id

    # Default output filename
    output_file = args.output if args.output else f"generated_profiles/plots/{args.profile_id}.png"

    plot_daily_profile(daily_profile, title, output_file, show=args.show)


if __name__ == '__main__':
    main()