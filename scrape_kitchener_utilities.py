#!/usr/bin/env python
"""
Scrape water/sewer bills from Kitchener Utilities.

Usage:
    # Download all available bills
    python scrape_kitchener_utilities.py

    # Store credentials
    python scrape_kitchener_utilities.py --store --account ACCOUNT_NUM --password PASS
"""

import sys
import os
import argparse
import keyring

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from utility_bill_scraper.canada.on.kitchener_utilities import KitchenerUtilitiesAPI

SERVICE_NAME = "kitchener-utilities"


def get_credentials():
    """Get credentials from keyring or environment variables."""
    # Try environment variables
    account = os.getenv("KU_ACCOUNT")
    password = os.getenv("KU_PASSWORD")
    if account and password:
        return account, password, "environment"

    # Try keyring
    account = keyring.get_password(SERVICE_NAME, "username")
    if account:
        password = keyring.get_password(SERVICE_NAME, account)
        if password:
            return account, password, "keyring"

    return None, None, None


def store_credentials(account, password):
    """Store credentials in keyring."""
    keyring.set_password(SERVICE_NAME, "username", account)
    keyring.set_password(SERVICE_NAME, account, password)
    print(f"✓ Credentials stored for account {account}")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape water/sewer bills from Kitchener Utilities"
    )
    parser.add_argument("--account", help="Account number")
    parser.add_argument("--password", help="Password")
    parser.add_argument("--store", action="store_true", help="Store credentials in keyring")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument("--contract", default="Water and Sewer",
                       help="Contract type (default: 'Water and Sewer')")
    args = parser.parse_args()

    # Get credentials
    account, password, source = get_credentials()

    # Override with command line
    if args.account:
        account = args.account
        source = "command line"
    if args.password:
        password = args.password

    # Store if requested
    if args.store:
        if not account or not password:
            print("❌ Error: --account and --password required with --store")
            return 1
        store_credentials(account, password)
        if not args.start and not args.end:
            return 0

    # Validate credentials
    if not account or not password:
        print("❌ Error: No credentials found")
        print("\nProvide credentials via:")
        print("  1. Command line: --account NUM --password PASS")
        print("  2. Environment: KU_ACCOUNT and KU_PASSWORD")
        print("  3. Keyring: Run with --store first")
        return 1

    print("=" * 70)
    print("Kitchener Utilities - Bill Scraper")
    print("=" * 70)
    print(f"\nAccount: {account}")
    print(f"Source: {source}")
    print(f"Contract: {args.contract}")
    print("=" * 70 + "\n")

    try:
        print("Connecting to ebilling.kitchener.ca...")
        api = KitchenerUtilitiesAPI(account, password)

        print(f"Downloading {args.contract} bills...")
        downloaded = api.download_statements(
            start_date=args.start,
            end_date=args.end
        )

        print(f"\n✓ SUCCESS!")
        print("=" * 70)
        print(f"Downloaded {len(downloaded)} PDF bills")
        print(f"Saved to: data/Kitchener Utilities/statements/")
        for f in downloaded:
            print(f"  - {os.path.basename(f)}")
        print("=" * 70)

        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
