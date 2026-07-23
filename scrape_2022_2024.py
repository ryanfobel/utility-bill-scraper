#!/usr/bin/env python3
"""
Scrape 2022-2024 hourly electricity data from Enova Power.

Usage:
  export ENOVA_USERNAME='your_username'
  export ENOVA_PASSWORD='your_password'
  pixi run python scrape_2022_2024.py
"""
import sys
import os
sys.path.insert(0, "src")

from utility_bill_scraper.canada.on.kitchener_wilmot_hydro import KitchenerWilmotHydroAPI


def main():
    print("="*60)
    print("Enova Power - Hourly Data Scraper (2022-2024)")
    print("="*60)
    print()

    username = os.getenv("ENOVA_USERNAME")
    password = os.getenv("ENOVA_PASSWORD")

    if not username or not password:
        print("❌ Missing credentials!")
        print()
        print("Set environment variables:")
        print("  export ENOVA_USERNAME='your_username'")
        print("  export ENOVA_PASSWORD='your_password'")
        print()
        return 1

    print(f"Username: {username}")
    print("Password: {'*' * len(password)}")
    print()
    print("Date range: 2022-01-01 to 2024-12-31")
    print()
    print("This will:")
    print("  1. Open Chrome browser")
    print("  2. Login to myaccount.enovapower.com")
    print("  3. Download CSV for each month (36 months)")
    print("  4. Parse and combine into hourly DataFrame")
    print()

    response = input("Continue? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled")
        return 0

    print()
    print("Starting scraper...")
    print()

    try:
        # Initialize API with visible browser so we can see progress
        api = KitchenerWilmotHydroAPI(
            user=username,
            password=password,
            headless=False,  # Set to True to hide browser
            browser="Chrome",
        )

        print("Downloading hourly data...")
        print()

        df = api.download_hourly_data(
            start_date="2022-01-01",
            end_date="2024-12-31"
        )

        if df is not None and len(df) > 0:
            print()
            print("="*60)
            print("✓ Success!")
            print("="*60)
            print(f"Downloaded: {len(df):,} hourly readings")
            print(f"Date range: {df.index.min()} to {df.index.max()}")
            print(f"Total kWh: {df['kWh'].sum():,.1f}")
            print()

            # Save to CSV
            output_file = "enova_hourly_2022_2024.csv"
            df.to_csv(output_file)
            print(f"✓ Saved to: {output_file}")
            print()
            print("Next steps:")
            print("  1. Copy CSV to energy-data-pipelines")
            print("  2. Load with Enova CSV pipeline")

            return 0
        else:
            print()
            print("❌ No data downloaded")
            return 1

    except Exception as e:
        print()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
