#!/usr/bin/env python
"""
Scrape hourly electricity usage data from Enova Power.

Usage:
    # Download all available data
    python scrape_enova.py

    # Download specific date range
    python scrape_enova.py --start 2025-01-01 --end 2025-12-31

    # Store credentials
    python scrape_enova.py --store --username user@example.com --password mypass
"""

import sys
import os
import argparse
import keyring
from datetime import datetime
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from utility_bill_scraper.canada.on.enova_power import EnovaPowerAPI

SERVICE_NAME = "enova-power"


def get_credentials():
    """Get credentials from keyring or environment variables."""
    # Try environment variables first
    username = os.getenv("ENOVA_USERNAME")
    password = os.getenv("ENOVA_PASSWORD")
    if username and password:
        return username, password, "environment"

    # Try keyring
    username = keyring.get_password(SERVICE_NAME, "username")
    if username:
        password = keyring.get_password(SERVICE_NAME, username)
        if password:
            return username, password, "keyring"

    return None, None, None


def store_credentials(username, password):
    """Store credentials in keyring."""
    keyring.set_password(SERVICE_NAME, "username", username)
    keyring.set_password(SERVICE_NAME, username, password)
    print(f"✓ Credentials stored in keyring for {username}")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape hourly electricity usage from Enova Power",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Download all available data
  %(prog)s --start 2025-01-01           # Download from Jan 2025 onwards
  %(prog)s --start 2025-01-01 --end 2025-12-31  # Specific range
  %(prog)s --store --username user@example.com --password mypass
        """
    )
    parser.add_argument("--username", help="Enova Power account username (email)")
    parser.add_argument("--password", help="Enova Power account password")
    parser.add_argument("--store", action="store_true", help="Store credentials in keyring")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD), defaults to 2022-01-01")
    parser.add_argument("--end", help="End date (YYYY-MM-DD), defaults to today")
    parser.add_argument("--output", help="Output CSV file (default: auto-generated)")
    parser.add_argument("--year", type=int, help="Download specific year only")
    args = parser.parse_args()

    # Get credentials
    username, password, source = get_credentials()

    # Override with command line args if provided
    if args.username:
        username = args.username
        source = "command line"
    if args.password:
        password = args.password

    # Store credentials if requested
    if args.store:
        if not username or not password:
            print("❌ Error: --username and --password required with --store")
            return 1
        store_credentials(username, password)
        if not args.start and not args.end and not args.year:
            return 0  # Just storing, exit

    # Validate credentials
    if not username or not password:
        print("❌ Error: No credentials found")
        print("\nProvide credentials via:")
        print("  1. Command line: --username <email> --password <password>")
        print("  2. Environment: ENOVA_USERNAME and ENOVA_PASSWORD")
        print("  3. Keyring: Run with --store --username --password first")
        return 1

    # Determine date range
    if args.year:
        start_date = f"{args.year}-01-01"
        end_date = f"{args.year}-12-31"
    else:
        start_date = args.start or "2022-01-01"
        end_date = args.end

    print("=" * 70)
    print("Enova Power - Hourly Data Scraper")
    print("=" * 70)
    print(f"\nUsername: {username}")
    print(f"Source: {source}")
    print(f"Date range: {start_date} to {end_date or 'today'}")
    print("\nNote: Enova Power typically has ~7 months of data available")
    print("=" * 70 + "\n")

    try:
        # Download data
        print("Connecting to Enova Power...")
        api = EnovaPowerAPI(username, password)

        print(f"Downloading data from {start_date}...")
        df = api.download_hourly_data(start_date, end_date)

        if len(df) == 0:
            print("\n⚠ No data downloaded")
            print("The requested date range may not have data available.")
            return 1

        # Determine output file
        if args.output:
            output_file = args.output
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"enova_hourly_data_{timestamp}.csv"

        # Save
        df.to_csv(output_file)

        # Summary
        print("\n" + "=" * 70)
        print("✓ SUCCESS!")
        print("=" * 70)
        print(f"Rows downloaded: {len(df):,}")
        print(f"Date range: {df.index.min()} to {df.index.max()}")
        print(f"Unique days: {len(set(df.index.date)):,}")
        print(f"Years covered: {sorted(set(df.index.year))}")
        print(f"\nSaved to: {output_file}")
        print("=" * 70)

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
