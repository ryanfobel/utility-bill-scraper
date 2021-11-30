# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.13.2
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/ryanfobel/utility-bill-scraper/main?labpath=notebooks%2Fcanada%2Fon%2Fkitchener_wilmot_hydro.ipynb)
#
# # Introduction
#
# This notebook demonstrates scraping of data from [Kitchener-Wilmot Hydro](https://www.kwhydro.on.ca) electricity bills. You can launch an interactive version of this page by clicking on the badge at the top of the page.
#
# ## Setup
#
# Fill in your `username` and `password` below, then run all of the cells in the notebook (press `SHIFT`+`ENTER` to run each cell individually or run the entire notebook by selecting `Run`/`Run all cells` from the menu. After the notebook finishes running (~1-5 minutes), you'll be able to download your data as a `download.zip` file (containing both a summary `monthly.csv` and the `*.pdf` statements).This file should appear in the file browser on the left and you can download it by `Right-clicking` on it and clicking `Download`.

# +
username = ""
password = ""

# Plotting preferences
bin_width = 0.9
alpha = 0.5
transparent = False
bbox_inches = "tight"
facecolor = "white"

# %matplotlib inline

import datetime as dt
import os
import shutil

import matplotlib.pyplot as plt
import numpy as np
from dotenv import load_dotenv
from matplotlib import rcParams
from cycler import cycler

import utility_bill_scraper.canada.on.kitchener_wilmot_hydro as kwh

# Scale the RGB values to the [0, 1] range, which is the format matplotlib accepts.    
def scale_rgb(colormap):
    return [(r / 255., g / 255., b / 255.) for r, g, b in colormap]

light = scale_rgb([
    (136, 189, 230),
    (251, 178, 88),
    (144, 205, 151),
    (246, 170, 201),
    (191, 165, 84),
    (188, 153, 199),
    (237, 221, 70),
    (240, 126, 110),
    (140, 140, 140)])

rcParams.update({
    'figure.figsize': (12, 6),
    'font.size': 12,
    'axes.prop_cycle': cycler('color', light)
})

# Load the `.env` file into the environment if it exists
load_dotenv()

# If we haven't set a username/password, try getting them from
# environment variables.
if not username:
    username = os.getenv("KWHYDRO_USER")
if not password:
    password = os.getenv("KWHYDRO_PASSWORD")

# Set the path where data is saved.
data_path = os.getenv("DATA_PATH", os.path.join("..", "..", "..", "data"))

# Get google service account credentials (if the environment variable is set).
google_sa_credentials = os.getenv("GOOGLE_SA_CREDENTIALS")

# Uncomment the following 2 lines for development
# %load_ext autoreload
# %autoreload 2

api = kwh.KitchenerWilmotHydroAPI(
    username,
    password,
    data_path,
    google_sa_credentials=google_sa_credentials,
)

# Get up to 24 statements (the most recent).
updates = api.update(24)
if updates is not None:
    print(f"{ len(updates) } statements_downloaded")
api.history("monthly").tail()
# -


# ## Monthly electricity consumption history

# +
df = api.history("monthly")

plt.figure()
df[['On Peak Consumption', 'Mid Peak Consumption', 'Off Peak Consumption']].plot.bar(
    stacked=True, width=bin_width, color=['#F07E6E', '#EDDD46', '#90CD97']
)
plt.ylim((0, None))
plt.title("Monthly Electricity Consumption")
plt.ylabel("kWh")
plt.legend(["Off Peak", "Mid Peak", "On Peak", "Total"])
plt.savefig(
    os.path.join("images", "monthly_electricity_consumption.png"),
    bbox_inches=bbox_inches,
    transparent=transparent,
    facecolor=facecolor,
)
# -
# ## Annual CO2 emissions

# +
# Carbon intensity of electricity generation in Ontario (40-77 g CO2 / kWh)
# * 40 g / kWh (https://www.neb-one.gc.ca/nrg/sttstc/lctrct/rprt/
#               2017cndrnwblpwr/ghgmssn-eng.html)
# * 77 g / kWh (https://www.conferenceboard.ca/hcp/provincial/environment/
#               low-emitting-electricity-production.aspx)
# * This is likely to go up when Pickering is closed
#   https://www.opg.com/darlington-refurbishment/Documents/IntrinsikReport_GHG_OntarioPower.pdf

carbon_intensity_kgCO2_per_kwh = 0.077

plt.figure()
df["kgCO2"] = df["Total Consumption"] * carbon_intensity_kgCO2_per_kwh
df["year"] = [int(x[0:4]) for x in df.index]
df["month"] = [int(x[5:7]) for x in df.index]
(df.groupby("year").sum()["kgCO2"] / 1e3).plot.bar(width=bin_width)
plt.title("Annual CO$_2$e emissions from electricity")
plt.ylabel("tCO$_2$e")
plt.savefig(
    os.path.join("images", "annual_co2_emissions_electricity.png"),
    bbox_inches=bbox_inches,
    transparent=transparent,
    facecolor=facecolor,
)

print(
    "annual electricity usage: %.1f kWh"
    % (df["Total Consumption"].iloc[-12:].sum())
)
print("annual electricity cost: $%.2f" % (df["Total"].iloc[-12:].sum()))
print(
    "annual CO2 emissions from electricity: %.2f kg"
    % (df["Total Consumption"].iloc[-12:].sum() * carbon_intensity_kgCO2_per_kwh)
)
# -

# ## CO2 emissions vs previous year

# +
n_years_history = 1

plt.figure()
for year, df_year in df.groupby("year"):
    if year >= dt.datetime.utcnow().year - n_years_history:
        df_year.sort_values("month", inplace=True)
        plt.bar(
            df_year["month"],
            df_year["Total Consumption"],
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
plt.title("Monthly CO$_2$e emissions from electricity")
plt.savefig(
    os.path.join("images", "monthly_co2_emissions_electricity.png"),
    bbox_inches=bbox_inches,
    transparent=transparent,
    facecolor=facecolor,
)

plt.figure()
for year, df_year in df.groupby("year"):
    if year >= dt.datetime.utcnow().year - n_years_history:
        df_year.sort_values("month", inplace=True)
        plt.bar(
            df_year["month"],
            np.cumsum(df_year["Total Consumption"]),
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
plt.title("Cumulative CO$_2$e emissions from electricity per year")
plt.savefig(
    os.path.join("images", "cumulative_co2_emissions_electricity.png"),
    bbox_inches=bbox_inches,
    transparent=transparent,
    facecolor=facecolor,
)
# -

# ## Save data as `downloads.zip` or print link to gdrive folder
#
# Generate a zip file with all of the data. `Right-click` on the file `downloads.zip` in the file browser on the left (it'll be in the `notebooks` folder). If `DATA_PATH` is a google drive link, print the url.

# +
from utility_bill_scraper import is_gdrive_path

if is_gdrive_path(data_path):
    print(data_path)
else:
    print(shutil.make_archive(os.path.join(".", "download"), "zip", data_path))
