# ---
# jupyter:
#   jupytext:
#     formats: py:light,ipynb
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.13.0
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# + [markdown] tags=[]
# # Introduction
#
# This notebook demonstrates scraping of data from the [Kitchener Utilities](https://www.kitchenerutilities.ca) website and gas & water bills (pdfs).
#
# ## Instructions
#
# Fill in your `username` and `password` below, then run all of the cells in the notebook. Data is saved in the directory `../data`.
# -

username = ""
password = ""

# +
# %load_ext autoreload
# %autoreload 2
# %matplotlib inline

import datetime as dt
import os
import sys

# Update the path to include the src directory
sys.path.insert(0, os.path.join("..", "src"))

import matplotlib.pyplot as plt
import numpy as np
from dotenv import load_dotenv
from matplotlib import rcParams

import utility_bill_scraper.kitchener_utilities as ku

# Load the `.env` file into the environment if it exists
load_dotenv()

rcParams.update({"figure.figsize": (12, 6)})

# If we haven't set a username/password, try getting them from
# environment variables.
if not username:
    username = os.getenv("KITCHENER_UTILITIES_USER")
if not password:
    password = os.getenv("KITCHENER_UTILITIES_PASSWORD", password)

# Set the path where data is saved.
data_path = os.path.join("..", "data")

ku_api = ku.KitchenerUtilitiesAPI(username, password, data_path)

# Get up to 24 statements (the most recent).
updates = ku_api.update(24)
if updates is not None:
    print(f"{ len(updates) } statements_downloaded")
ku_api.history().tail()

# +
# Plot consumption history
df_ku = ku_api.history()

plt.figure()
plt.bar(df_ku.index, df_ku["Gas Consumption"], width=0.9)
plt.xticks(rotation=90)
plt.title("Monthly Gas Consumption")
plt.ylabel("m$^3$")

plt.figure()
plt.bar(df_ku.index, df_ku["Water Consumption"], width=0.9)
plt.xticks(rotation=90)
plt.title("Monthly Water Consumption")
plt.ylabel("m$^3$")

# +
# Plot annual CO2 emissions

from utility_bill_scraper import GAS_KGCO2_PER_CUBIC_METER

df_ku["kgCO2"] = df_ku["Gas Consumption"] * GAS_KGCO2_PER_CUBIC_METER
df_ku["year"] = [int(x[0:4]) for x in df_ku.index]
df_ku["month"] = [int(x[5:7]) for x in df_ku.index]

plt.figure()
df_ku.groupby("year").sum()["Gas Consumption"].plot.bar(width=0.9)
plt.ylabel("m$^3$")
ylim = plt.ylim()
ax = plt.gca()
ax2 = ax.twinx()
plt.ylabel("tCO$_2$e")
plt.ylim([GAS_KGCO2_PER_CUBIC_METER * y / 1e3 for y in ylim])
plt.title("Annual home CO$_2$e emissions from natural gas")

# +
# Plot CO2 emissions vs previous year
n_years_history = 1

plt.figure()
for year, df_year in df_ku.groupby("year"):
    if year >= dt.datetime.utcnow().year - n_years_history:
        df_year.sort_values("month")
        plt.bar(
            df_year["month"],
            df_year["Gas Consumption"],
            label=year,
            alpha=0.5,
            width=0.9,
        )
plt.legend()
plt.ylabel("m$^3$")
plt.xlabel("Month")
ylim = plt.ylim()
ax = plt.gca()
ax2 = ax.twinx()
plt.ylabel("tCO$_2$e")
plt.ylim([GAS_KGCO2_PER_CUBIC_METER * y / 1e3 for y in ylim])
plt.title("Monthly home CO$_2$e emissions from natural gas")

plt.figure()
for year, df_year in df_ku.groupby("year"):
    if year >= dt.datetime.utcnow().year - n_years_history:
        df_year.sort_values("month", inplace=True)
        plt.bar(
            df_year["month"],
            np.cumsum(df_year["Gas Consumption"]),
            label=year,
            alpha=0.5,
            width=0.9,
        )
plt.legend()
plt.ylabel("m$^3$")
plt.xlabel("Month")
ylim = plt.ylim()
ax = plt.gca()
ax2 = ax.twinx()
plt.ylabel("tCO$_2$e")
plt.ylim([GAS_KGCO2_PER_CUBIC_METER * y / 1e3 for y in ylim])
plt.title("Cumulative CO$_2$e emissions from natural gas per year")
# -
