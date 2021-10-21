# Utility bill scraper

[![build](https://github.com/ryanfobel/utility-bill-scraper/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/ryanfobel/utility-bill-scraper/actions/workflows/build.yml)
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/ryanfobel/utility-bill-scraper/main)
[![PyPI version shields.io](https://img.shields.io/pypi/v/utility-bill-scraper.svg)](https://pypi.python.org/pypi/utility-bill-scraper/)

Download energy usage data and estimate CO2 emissions from utility websites or pdf bills.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
## Table of contents

- [Supported utilities](#supported-utilities)
- [Install](#install)
- [Data storage](#data-storage)
- [Getting and plotting data using the Python API](#getting-and-plotting-data-using-the-python-api)
  - [Update data](#update-data)
  - [Plot monthly gas consumption](#plot-monthly-gas-consumption)
  - [Convert gas consumption to CO2 emissions](#convert-gas-consumption-to-co2-emissions)
  - [Plot CO2 emissions versus previous years](#plot-co2-emissions-versus-previous-years)
- [Command line utilities](#command-line-utilities)
  - [Update data](#update-data-1)
  - [Export data](#export-data)
  - [Options](#options)
  - [Environment variables](#environment-variables)
- [Contributors](#contributors)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Supported utilities

The simplest way to get started is to click on one of the following links, which will open a session on https://mybinder.org where you can try downloading some data. **Note: after you click on the link, it will take a couple of minutes to load an interactive Jupyter notebook.** Then follow the instructions (e.g., provide your `username` and `password`) to run the notebook directly from your browser.

 * [Kitchener Utilities (gas & water)](https://mybinder.org/v2/gh/ryanfobel/utility-bill-scraper/main?labpath=notebooks%2Fcanada%2Fon%2Fkitchener_utilities.ipynb)
 
## Install

```sh
pip install utility-bill-scraper
```

## Data storage

All data is stored in a file located at `$DATA_PATH/$UTILITY_NAME/data.csv`. The path to this file can be set as input argument when initializing an API object via the `data_path` argument.

```
└───data
    └───Kitchener Utilities
        └───data.csv
        └───statements
            │───2021-10-18 - Kitchener Utilities - $102.30.pdf
            ...
            └───2021-06-15 - Kitchener Utilities - $84.51.pdf
```

## Getting and plotting data using the Python API

### Update data

```python
import utility_bill_scraper.canada.on.kitchener_utilities as ku

ku_api = ku.KitchenerUtilitiesAPI(username='username', password='password')

# Get new statements.
updates = ku_api.update()
if updates is not None:
    print(f"{ len(updates) } statements_downloaded")
ku_api.history().tail()
```
![history tail](https://raw.githubusercontent.com/ryanfobel/utility-bill-scraper/main/notebooks/canada/on/images/history_tail.png)




### Plot monthly gas consumption

```python
import matplotlib.pyplot as plt

df_ku = ku_api.history()

plt.figure()
plt.bar(df_ku.index, df_ku["Gas Consumption"], width=0.9, alpha=0.5)
plt.xticks(rotation=90)
plt.title("Monthly Gas Consumption")
plt.ylabel("m$^3$")
```

![monthly gas consumption](https://raw.githubusercontent.com/ryanfobel/utility-bill-scraper/main/notebooks/canada/on/images/monthly_gas_consumption.png)

### Convert gas consumption to CO2 emissions

```python
from utility_bill_scraper import GAS_KGCO2_PER_CUBIC_METER

df_ku["kgCO2"] = df_ku["Gas Consumption"] * GAS_KGCO2_PER_CUBIC_METER
```

### Plot CO2 emissions versus previous years

```python
import datetime as dt

df_ku["kgCO2"] = df_ku["Gas Consumption"] * GAS_KGCO2_PER_CUBIC_METER
df_ku["year"] = [int(x[0:4]) for x in df_ku.index]
df_ku["month"] = [int(x[5:7]) for x in df_ku.index]

n_years_history = 1

plt.figure()
for year, df_year in df_ku.groupby("year"):
    if year >= dt.datetime.utcnow().year - n_years_history:
        df_year.sort_values("month", inplace=True)
        plt.bar(
            df_year["month"],
            df_year["Gas Consumption"],
            label=year,
            width=0.9,
            alpha=0.5,
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
![monthly_co2_emissions](https://raw.githubusercontent.com/ryanfobel/utility-bill-scraper/main/notebooks/canada/on/images/monthly_co2_emissions.png)

## Command line utilities

Update and export your utility data from the command line.

### Update data

```sh
> python -m utility_bill_scraper.bin.ubs --utilty-name "Kitchener Utilities" update --user $USER --password $PASSWORD
```

### Export data

```sh
> python -m utility_bill_scraper.bin.ubs --utilty-name "Kitchener Utilities" export --output data.csv
```

### Options

```sh
> python -m utility_bill_scraper.bin.ubs --help
usage: ubs.py [-h] [-e ENV] [--data-path DATA_PATH] [--utility-name UTILITY_NAME]
              [--google-sa-credentials GOOGLE_SA_CREDENTIALS]
              {update,export} ...

ubs (Utility bill scraper)

optional arguments:
  -h, --help            show this help message and exit
  -e ENV, --env ENV     path to .env file
  --data-path DATA_PATH
                        folder containing the data file and statements
  --utility-name UTILITY_NAME
                        name of the utility
  --google-sa-credentials GOOGLE_SA_CREDENTIALS
                        google service account credentials

subcommands:
  {update,export}       available sub-commands
```

### Environment variables

Note that many options can be set via environment variables (useful for continuous integration and/or working with containers). The following can be set in your shell or via a `.env` file passed using the `-e` option.

```sh
DATA_PATH="folder containing the data file and statements"
UTILITY_NAME="name of the utility"
GOOGLE_SA_CREDENTIALS="google service account credentials"
USER="username"
PASSWORD="password"
SAVE_STATEMENTS="save downloaded statements (default=True)"
MAX_DOWNLOADS="maximum number of statements to download"
```

## Contributors

* Ryan Fobel ([@ryanfobel](https://github.com/ryanfobel))
