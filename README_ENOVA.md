# Enova Power Scraper

Download hourly electricity usage data from Enova Power (formerly Kitchener-Wilmot Hydro).

## Quick Start

```bash
# Install dependencies
pixi install

# Download all available data
pixi run python scrape_enova.py

# Download specific year
pixi run python scrape_enova.py --year 2025

# Download specific date range
pixi run python scrape_enova.py --start 2025-01-01 --end 2025-06-30
```

## Setup Credentials

Store your Enova Power login credentials securely:

```bash
pixi run python scrape_enova.py --store --username your.email@example.com --password yourpassword
```

Or use environment variables:
```bash
export ENOVA_USERNAME="your.email@example.com"
export ENOVA_PASSWORD="yourpassword"
pixi run python scrape_enova.py
```

## What You Get

Downloads hourly electricity usage as CSV:

```csv
Datetime,kWh
2025-01-01 00:00:00,0.00
2025-01-01 01:00:00,0.71
2025-01-01 02:00:00,0.70
...
```

## Data Availability

Enova Power's "Electric Downloads" feature typically provides:
- **~7 months** of historical data
- **Hourly** granularity
- Automatically detects what's actually available

Historical data beyond this window is not accessible via web scraping.

## How It Works

1. Logs into `myaccount.enovapower.com`
2. Navigates to Electric Downloads page
3. Sets date range and selects "Hourly" data
4. Downloads CSV via "Spreadsheet Download" button
5. Parses and formats into proper timestamps

## Programmatic Usage

```python
from utility_bill_scraper.canada.on.enova_power import EnovaPowerAPI

api = EnovaPowerAPI(username, password)
df = api.download_hourly_data("2025-01-01", "2025-12-31")
df.to_csv("my_usage.csv")
```

## Migration Note

This scraper was updated for the Enova Power rebrand:
- **Old:** Kitchener-Wilmot Hydro (`kwhydro.on.ca`)
- **New:** Enova Power (`myaccount.enovapower.com`)

The old `KitchenerWilmotHydroAPI` class name still works for backward compatibility but is deprecated.

## Troubleshooting

**No data for old dates?**
- Enova Power only keeps ~7 months online
- For older data, check email bills or contact customer service

**Login fails?**
- Verify credentials at https://myaccount.enovapower.com
- Check if account is locked or password expired

**Import errors?**
- Use `EnovaPowerAPI` from `enova_power` module
- Old `KitchenerWilmotHydroAPI` imports still work but show deprecation warning

## Recent Changes (July 2024)

- ✅ Fixed for new Enova Power website
- ✅ Updated to Electric Downloads page (not Smart Meter chart)
- ✅ Fixed CSV parsing (trailing comma issue)
- ✅ Modern Selenium and Pandas APIs
- ✅ Renamed module to `enova_power`
