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
# ## Setup instructions:
#
# 1. Download the [firefox webdriver](https://github.com/mozilla/geckodriver/releases/) and put it somewhere on your path.
#
# 2. Create a new text file called `.env` in this directory to provide your login credentials (i.e., replace `username` and `password`):
#
# ```sh
# KITCHENER_UTILITIES_USER=username
# KITCHENER_UTILITIES_PASSWORD=password
# ```

# +
# %load_ext autoreload
# %autoreload 2

import sys
import os
import datetime as dt

sys.path.insert(0, os.path.join("..", "src"))

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import rcParams
from dotenv import load_dotenv

import utility_bill_scraper.kitchener_utilities as ku

load_dotenv()

# %matplotlib inline

rcParams.update({"figure.figsize": (12, 6)})

history_path = os.path.abspath(os.path.join("..", "data", "Kitchener Utilities", "data.csv"))
statement_path = os.path.abspath(os.path.join("..", "data", "Kitchener Utilities", "statements"))

# +
# Create a Kitchener Utilities API object with your user name and password
username = os.getenv("KITCHENER_UTILITIES_USER")
password = os.getenv("KITCHENER_UTILITIES_PASSWORD")

ku_api = ku.KitchenerUtilitiesAPI(username, password, history_path, statement_path)

ku_api.update()
ku_api.history().tail()

# +
df_ku = ku_api.history()

plt.figure()
plt.bar(df_ku.index, df_ku["Gas Consumption"], width=0.9)
plt.xticks(rotation=90)
plt.title("Gas Consumption")
plt.ylabel("m$^3$")

plt.figure()
plt.bar(df_ku.index, df_ku["Water Consumption"], width=0.9)
plt.xticks(rotation=90)
plt.title("Water Consumption")
plt.ylabel("m$^3$")

# +
# Natural gas emission factor
# 119.58 lbs CO2/1000 cubic feet of natural gas
# 1.915 kg CO2/1 m^3 natural gas [119.58 lbs * (1 kg / 2.204623 lbs) *
#   (1 ft^3 / (0.0254 * 12)**3 m^3) / 1000]
kgCO2_per_cubic_meter = 119.58 * (1 / 2.204623) * (1 / (0.0254 * 12) ** 3) / 1000  # kg CO2/1 m^3 natural gas

# gas_variable_rate = df_gas['Gas Variable Rate'].iloc[-12:].mean()  # $ / m^3

# Natural gas energy density
# 1,037 Btu / ft^3 (https://www.eia.gov/tools/faqs/faq.php?id=45&t=8)
# Energy per m^3: 1,037 Btu / ft^3 * 1055.1 J / 1 Btu * 1 ft^3 /
#   (0.0254 * 12)**3 m^3
#   37 MJ/m3 (https://hypertextbook.com/facts/2002/JanyTran.shtml)

joules_per_cubic_meter = 1037 * 1055.1 / (0.0254 * 12) ** 3  # J / m^3
kwh_per_joule = 1.0 / (60 * 60 * 1000)
kwh_per_cubic_meter = joules_per_cubic_meter * kwh_per_joule

df_ku["kgCO2"] = df_ku["Gas Consumption"] * kgCO2_per_cubic_meter
df_ku["year"] = [int(x[0:4]) for x in df_ku.index]
df_ku["month"] = [int(x[5:7]) for x in df_ku.index]
# -

plt.figure()
df_ku.groupby("year").sum()["Gas Consumption"].plot.bar(width=0.9)
plt.ylabel("m$^3$")
ylim = plt.ylim()
ax = plt.gca()
ax2 = ax.twinx()
plt.ylabel("tCO$_2$e")
plt.ylim([kgCO2_per_cubic_meter * y / 1e3 for y in ylim])
plt.title("Annual home CO$_2$e emissions from natural gas")

# +
n_years_history = 1

plt.figure()
for year, df_year in df_ku.groupby("year"):
    if year >= dt.datetime.utcnow().year - n_years_history:
        df_year.sort_values("month")
        plt.plot(df_year["month"], df_year["Gas Consumption"], label=year)
plt.legend()
plt.ylabel("m$^3$")
plt.xlabel("Month")
ylim = plt.ylim()
ax = plt.gca()
ax2 = ax.twinx()
plt.ylabel("tCO$_2$e")
plt.ylim([kgCO2_per_cubic_meter * y / 1e3 for y in ylim])
plt.title("Monthly home CO$_2$e emissions from natural gas")

plt.figure()
for year, df_year in df_ku.groupby("year"):
    if year >= dt.datetime.utcnow().year - n_years_history:
        df_year.sort_values("month")
        plt.plot(df_year["month"], np.cumsum(df_year["Gas Consumption"]), label=year)
plt.legend()
plt.ylabel("m$^3$")
plt.xlabel("Month")
ylim = plt.ylim()
ax = plt.gca()
ax2 = ax.twinx()
plt.ylabel("tCO$_2$e")
plt.ylim([kgCO2_per_cubic_meter * y / 1e3 for y in ylim])
plt.title("Cumulative CO$_2$e emissions from natural gas per year")

# -
