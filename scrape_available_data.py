#!/usr/bin/env python
"""
Scrape all available hourly electricity usage data from Enova Power.
Automatically detects the date range that has data available.
"""

import sys
import os
import keyring
from datetime import datetime, timedelta
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from utility_bill_scraper.canada.on.kitchener_wilmot_hydro import KitchenerWilmotHydroAPI

SERVICE_NAME = "enova-power"

# Get credentials
username = keyring.get_password(SERVICE_NAME, "username")
password = keyring.get_password(SERVICE_NAME, username) if username else None

if not username or not password:
    print("❌ Error: No credentials found in keyring")
    sys.exit(1)

print("=" * 70)
print("Enova Power - Smart Hourly Data Scraper")
print("=" * 70)
print(f"\nUsername: {username}")
print("\nThis will automatically detect and download all available data.")
print("Starting in 2 seconds...")
import time
time.sleep(2)

print("\n" + "=" * 70)
print("Starting smart scraper...")
print("=" * 70 + "\n")

try:
    api = KitchenerWilmotHydroAPI(username, password)

    # Try to download data year by year, starting from 2022
    all_data = []
    start_year = 2022
    current_year = datetime.now().year

    for year in range(start_year, current_year + 1):
        print(f"\n📅 Trying year {year}...")

        try:
            # Try to download the full year
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"

            df = api.download_hourly_data(start_date, end_date)

            if len(df) > 0:
                print(f"   ✓ Got {len(df)} rows for {year}")
                print(f"   Date range: {df.index.min()} to {df.index.max()}")
                all_data.append(df)
            else:
                print(f"   ⚠ No data available for {year}")

        except Exception as e:
            error_msg = str(e)
            if "No columns to parse" in error_msg or "No consumption history" in error_msg:
                print(f"   ⚠ No data available for {year}")
            else:
                print(f"   ❌ Error for {year}: {e}")

    # Combine all data
    if all_data:
        print("\n" + "=" * 70)
        print("Combining data...")
        print("=" * 70)

        combined_df = pd.concat(all_data)
        combined_df = combined_df.sort_index()

        # Save to CSV
        output_file = f"enova_hourly_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        combined_df.to_csv(output_file)

        print(f"\n✅ SUCCESS!")
        print("=" * 70)
        print(f"Total rows: {len(combined_df)}")
        print(f"Date range: {combined_df.index.min()} to {combined_df.index.max()}")
        print(f"Unique days: {len(set(combined_df.index.date))}")
        print(f"Years covered: {sorted(set(combined_df.index.year))}")
        print(f"\nSaved to: {output_file}")
        print("=" * 70)

    else:
        print("\n❌ No data was available for any year tested")
        sys.exit(1)

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
