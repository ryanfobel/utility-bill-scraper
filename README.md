<!-- #region tags=[] -->
# Utility bill scraper

[![build](https://github.com/ryanfobel/utility-bill-scraper/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/ryanfobel/utility-bill-scraper/actions/workflows/build.yml)
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/ryanfobel/utility-bill-scraper/main)
[![PyPI version shields.io](https://img.shields.io/pypi/v/utility-bill-scraper.svg)](https://pypi.python.org/pypi/utility-bill-scraper/)

Download energy usage and carbon emissions data from utility websites or pdf bills.

## Install

```sh
pip install utility-bill-scraper
```

## Supported utilities

The simplest way to get started without installing anything on your computer is to click on one of the following links, which will open a session on https://mybinder.org where you can try downloading some data.

 * [Kitchener Utilities (gas & water)](https://mybinder.org/v2/gh/ryanfobel/utility-bill-scraper/main?labpath=notebooks%2Fcanada%2Fon%2Fkitchener_utilities.ipynb)
<!-- #endregion -->

<!-- #region -->
## Get updates

```python
import utility_bill_scraper.canada.on.kitchener_utilities as ku

ku_api = ku.KitchenerUtilitiesAPI(username, password)

# Get new statements.
updates = ku_api.update()
if updates is not None:
    print(f"{ len(updates) } statements_downloaded")
ku_api.history().tail()
```
![history tail](https://raw.githubusercontent.com/ryanfobel/utility-bill-scraper/main/notebooks/canada/on/images/history_tail.png)
<!-- #endregion -->

<!-- #region -->
## Plot monthly gas consumption

```python
df_ku = ku_api.history()

plt.figure()
plt.bar(df_ku.index, df_ku["Gas Consumption"], width=bin_width, alpha=alpha)
plt.xticks(rotation=90)
plt.title("Monthly Gas Consumption")
plt.ylabel("m$^3$")
```
![monthly gas consumption](https://raw.githubusercontent.com/ryanfobel/utility-bill-scraper/main/notebooks/canada/on/images/monthly_gas_consumption.svg)
<!-- #endregion -->

<!-- #region -->
## Convert gas consumption to CO2 emissions

```python
from utility_bill_scraper import GAS_KGCO2_PER_CUBIC_METER

df_ku["kgCO2"] = df_ku["Gas Consumption"] * GAS_KGCO2_PER_CUBIC_METER
```
<!-- #endregion -->

<!-- #region -->
## Plot CO2 emissions versus previous years

```python
n_years_history = 1

plt.figure()
for year, df_year in df_ku.groupby("year"):
    if year >= dt.datetime.utcnow().year - n_years_history:
        df_year.sort_values("month", inplace=True)
        plt.bar(
            df_year["month"],
            df_year["Gas Consumption"],
            label=year,
            width=bin_width,
            alpha=alpha,
        )
plt.legend()
plt.ylabel("m$^3$")
plt.xlabel("Month")
ylim = plt.ylim()
ax = plt.gca()
ax2 = ax.twinx()
plt.ylabel("tCO$_2$e")
plt.ylim([GAS_KGCO2_PER_CUBIC_METER * y / 1e3 for y in ylim])
plt.title("Monthly CO$_2$e emissions from natural gas")
```
![monthly_co2_emissions](https://raw.githubusercontent.com/ryanfobel/utility-bill-scraper/main/notebooks/canada/on/images/monthly_co2_emissions.svg)
<!-- #endregion -->

## Contributors

* [Ryan Fobel](https://github.com/ryanfobel)

```python

```
