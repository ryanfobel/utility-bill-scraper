# Enova Power Scraper Status

## Current Status: ✅ Working (with limitations)

Last updated: 2026-07-23

## What Works

- ✅ Login to Enova Power website (myaccount.enovapower.com)
- ✅ Navigate to Smart Meter consumption page
- ✅ Download hourly electricity usage data as CSV
- ✅ Parse and format the data correctly
- ✅ Save data to local files

## Known Limitations

### Historical Data Not Available
**The Enova Power website only provides approximately 30 days of recent data through the web interface.**

- Requesting historical dates (e.g., 2022-2024) will still only return the most recent ~30 days
- URL parameters for custom date ranges are ignored by the website
- The website has changed significantly since the Kitchener-Wilmot Hydro rebrand to Enova Power

### Workarounds for Historical Data

If you need historical electricity usage data, consider:

1. **Monthly Bills**: Download PDF bills from the "Bills & Payment" section
2. **Customer Service**: Contact Enova Power directly to request historical data export
3. **API Access**: Check if Enova Power offers an API for customers (unlikely but worth asking)
4. **Regular Scraping**: Run the scraper regularly (e.g., weekly) to build up a historical dataset going forward

## Changes Made During Migration

### URL Updates
- Old: `https://www3.kwhydro.on.ca`
- New: `https://myaccount.enovapower.com`

### Code Updates
1. Updated Selenium selectors for new page structure
2. Fixed deprecated Pandas methods (`freq="M"` → `freq="ME"`, `.append()` → `pd.concat()`)
3. Updated login button ID: `login_btn`
4. Updated download button ID: `download` → `downloadButton`
5. Fixed hourly data parsing to handle new CSV format

## Usage

### Download Recent Data
```bash
pixi run python scrape_recent.py
```

This will download the most recent ~30 days of hourly electricity usage data.

### Setup Credentials
```bash
# Store credentials in keyring
pixi run python -c "
import keyring
SERVICE = 'enova-power'
keyring.set_password(SERVICE, 'username', 'your_email@example.com')
keyring.set_password(SERVICE, 'your_email@example.com', 'your_password')
"
```

Or use the helper script:
```bash
./store_creds.sh
```

## Data Format

The scraper produces CSV files with hourly electricity consumption:

```csv
Datetime,kWh
2026-06-23 00:00:00,0.0
2026-06-23 01:00:00,0.45
2026-06-23 02:00:00,0.58
...
```

## Technical Notes

- Browser: Chrome (headless by default)
- Wait times: 5-10 seconds between requests to avoid rate limiting
- Data location: `./data/Kitchener-Wilmot Hydro/hourly.csv`

## Future Improvements

- [ ] Add email parsing to extract usage data from monthly bill emails
- [ ] Implement regular scheduled runs to build historical database
- [ ] Add data validation and gap detection
- [ ] Create visualization dashboard for usage data
