# Utility Bill Scrapers - Status Report

## Available Scrapers

### 1. ⚡ Enova Power (Electricity) - ✅ WORKING

**Status:** Fully updated and tested (July 2024)

**What it does:**
- Downloads hourly electricity usage data
- Historical data available: ~7 months
- Format: CSV with timestamps and kWh

**Module:** `src/utility_bill_scraper/canada/on/enova_power.py`

**Usage:**
```bash
pixi run python scrape_enova.py --year 2026
```

**Credentials stored:** ✅ Yes (ryan@fobel.net)

**Recent changes:**
- ✅ Updated for new Enova Power website (formerly KW Hydro)
- ✅ Fixed CSV parsing
- ✅ Modern Selenium API
- ✅ Modern Pandas API

---

### 2. 💧 Kitchener Utilities (Water/Sewer) - ✅ FIXED

**Status:** Updated to modern Selenium API (July 2024)

**What it does:**
- Downloads PDF bills for water, sewer, stormwater
- Historical statements available

**Module:** `src/utility_bill_scraper/canada/on/kitchener_utilities.py`

**Website:** https://ebilling.kitchener.ca

**Usage:**
```bash
pixi run python scrape_kitchener_utilities.py
```

**Credentials stored:** ⚠️ Not yet (need your account number)

**Recent changes:**
- ✅ Updated all Selenium API calls (15 instances)
- ✅ Modern By.* methods
- ✅ Created user-friendly script

**To use:**
1. Store credentials:
   ```bash
   python scrape_kitchener_utilities.py --store --account NUM --password PASS
   ```
2. Download bills:
   ```bash
   python scrape_kitchener_utilities.py
   ```

---

### 3. 🔥 Enbridge (Gas) - PDF PARSER ONLY

**Status:** No web scraper

**What it does:**
- Parses data from PDF bills
- No automated download capability

**Module:** `src/utility_bill_scraper/canada/on/enbridge.py`

**Usage:**
- Manual: Download PDF bills from Enbridge website
- Parse locally with this module

**Note:** Would need to create a web scraper to automate downloads

---

## Summary Matrix

| Utility | Type | Web Scraper | Status | Needs Work |
|---------|------|-------------|--------|------------|
| Enova Power | Electricity | ✅ Yes | ✅ Working | None |
| Kitchener Utilities | Water/Sewer | ✅ Yes | ✅ Fixed | Testing |
| Enbridge | Gas | ❌ No | N/A | Create scraper |

## Recommendations

### Priority 1: Fix Kitchener Utilities Scraper
**Effort:** Low (similar to Enova Power fixes)
**Value:** High (water bills have good historical data)

Steps:
1. Update Selenium API calls (15 instances)
2. Test if website structure changed
3. Verify download functionality

### Priority 2: Create Enbridge Web Scraper
**Effort:** Medium-High
**Value:** Medium (complete the trio)

Would need to:
1. Investigate Enbridge online portal
2. Determine if they provide downloadable usage data
3. Build scraper if available

## Testing Status

- ✅ Enova Power: Tested, downloaded 174 days of data
- ✅ Kitchener Utilities: Code updated, ready to test (need credentials)
- ❌ Enbridge: No scraper to test

## Next Steps

**To test Kitchener Utilities:**
1. Provide account number and password
2. Run: `python scrape_kitchener_utilities.py --store --account NUM --password PASS`
3. Download bills: `python scrape_kitchener_utilities.py`

**For Enbridge (Gas):**
- Would need to investigate if they offer downloadable data
- Create web scraper if available
