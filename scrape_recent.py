#!/usr/bin/env python
"""
Scrape recent hourly electricity usage data from Enova Power.

Note: The Enova Power website only provides approximately 30 days of recent data.
Historical data from 2022-2024 is not available through the web interface.
"""

import sys
import os
import argparse
import keyring
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from utility_bill_scraper.canada.on.kitchener_wilmot_hydro import KitchenerWilmotHydroAPI

SERVICE_NAME = "enova-power"


def get_credentials():
    """Get credentials from keyring or environment variables."""
    # Try environment variables first
    username = os.getenv("ENOVA_USERNAME")
    password = os.getenv("ENOVA_PASSWORD")

    if username and password:
        return username, password

    # Try keyring
    username = keyring.get_password(SERVICE_NAME, "username")
    if username:
        password = keyring.get_password(SERVICE_NAME, username)
        if password:
            return username, password

    return None, None


def store_credentials(username, password):
    """Store credentials in keyring."""
    keyring.set_password(SERVICE_NAME, "username", username)
    keyring.set_password(SERVICE_NAME, username, password)
    print(f"✓ Credentials stored in keyring for {username}")


def main():
    parser = argparse.ArgumentParser(description="Scrape recent Enova Power hourly data")
    parser.add_argument("--username", help="Enova Power username (email)")
    parser.add_argument("--password", help="Enova Power password")
    parser.add_argument("--store", action="store_true", help="Store credentials in keyring")
    parser.add_argument("--output", help="Output CSV file (default: enova_hourly_YYYYMMDD.csv)")
    args = parser.parse_args()

    # Get credentials
    username, password = get_credentials()

    # Use command line args if provided
    if args.username:
        username = args.username
    if args.password:
        password = args.password

    if not username or not password:
        print("❌ Error: No credentials found")
        print()
        print("Please provide credentials via:")
        print("  1. Command line: --username <email> --password <password>")
        print("  2. Environment: ENOVA_USERNAME and ENOVA_PASSWORD")
        print("  3. Keyring: Run with --username --password --store first")
        return 1

    # Store credentials if requested
    if args.store:
        store_credentials(username, password)
        if not args.output and not sys.stdin.isatty():
            # If only storing, exit
            return 0

    print("=" * 60)
    print("Enova Power - Recent Hourly Data Scraper")
    print("=" * 60)
    print()
    print(f"Username: {username}")
    print(f"Source: {'keyring' if keyring.get_password(SERVICE_NAME, username) else 'command line/env'}")
    print()
    print("NOTE: Enova Power only provides ~30 days of recent data")
    print("      Historical data is not available via web scraping")
    print()

    # Confirm
    if sys.stdin.isatty():
        response = input("Continue? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled")
            return 0

    print()
    print("Starting scraper...")
    print()

    try:
        # Initialize API
        api = KitchenerWilmotHydroAPI(username, password)

        # Download recent data (will get whatever is available, typically ~30 days)
        print("Downloading recent hourly data...")
        df = api.download_hourly_data()

        if len(df) == 0:
            print("❌ No data downloaded")
            return 1

        # Determine output file
        if args.output:
            output_file = args.output
        else:
            date_str = datetime.now().strftime("%Y%m%d")
            output_file = f"enova_hourly_{date_str}.csv"

        # Save to CSV
        df.to_csv(output_file)

        # Print summary
        print()
        print("=" * 60)
        print("✓ Success!")
        print("=" * 60)
        print(f"Rows downloaded: {len(df)}")
        print(f"Date range: {df.index.min()} to {df.index.max()}")
        print(f"Days of data: {df.index.date.nunique()}")
        print(f"Saved to: {output_file}")
        print()

        return 0

    except Exception as e:
        print()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
