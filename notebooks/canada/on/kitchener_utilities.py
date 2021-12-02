# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.13.2
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ryanfobel/utility-bill-scraper/blob/main/notebooks%2Fcanada%2Fon%2Fkitchener_utilities.ipynb)
#
# # Introduction
#
# This notebook will help you to download `pdf` statements and data from a [Kitchener Utilities](https://www.kitchenerutilities.ca) account. Launch an interactive version by clicking on the `Open in Colab` badge at the top of this page.
#
# ## Install dependencies
#
# First we need to install some dependencies. Click on the cell below, then either click the play button or press `SHIFT`+`ENTER`. The notebook may promp you for inputs (e.g., authorization to conect to your google drive, username, password). If you are running this notebook in Google Colab, you will need to restart the runtime afterwards by clicking `Runtime/Restart runtime` from the menu.

# %%
try:
    pass
except ModuleNotFoundError:
    import subprocess
    import sys

    cmd = (
        f"{sys.executable} -m pip install --upgrade --upgrade-strategy "
        "only-if-needed mypackage utility-bill-scraper"
    )
    subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode("utf-8")

from utility_bill_scraper import install_colab_dependencies

install_colab_dependencies(
    required_envs=["KITCHENER_UTILITIES_USER", "KITCHENER_UTILITIES_PASSWORD"]
)

# %% [markdown] tags=[] jp-MarkdownHeadingCollapsed=true
# # Downloading data
#
# Run the rest of the cells in the notebook (press `SHIFT`+`ENTER` to run each cell individually or run the entire notebook by selecting `Run`/`Run all cells` from the menu. After the notebook finishes running (~1-5 minutes), you'll be able to download your data as a `download.zip` file (containing both a summary `monthly.csv` and the `*.pdf` statements). This file should appear in the file browser on the left and you can download it by `Right-clicking` on it and clicking `Download`. Alternatively, if you're running this in Google Colab, the files will be automatically saved to your Google Drive in the folder `Google Drive/Colab Notebooks/data`.

# %%
# %matplotlib inline

import datetime as dt
import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from dotenv import load_dotenv
from matplotlib import rcParams

import utility_bill_scraper.canada.on.kitchener_utilities as ku
from utility_bill_scraper import install_colab_dependencies

install_colab_dependencies(
    required_envs=["KITCHENER_UTILITIES_USER", "KITCHENER_UTILITIES_PASSWORD"]
)

# Plotting preferences
bin_width = 0.9
alpha = 0.5
transparent = False
bbox_inches = "tight"
facecolor = "white"
rcParams.update({"figure.figsize": (12, 6)})

# Load the `.env` file into the environment if it exists
load_dotenv()

api = ku.KitchenerUtilitiesAPI(
    user=os.getenv("KITCHENER_UTILITIES_USER"),
    password=os.getenv("KITCHENER_UTILITIES_PASSWORD"),
    data_path=os.getenv("DATA_PATH", os.path.join("..", "..", "..", "data")),
    google_sa_credentials=os.getenv("GOOGLE_SA_CREDENTIALS"),
    browser=os.getenv("BROWSER", "Firefox"),
)

# Get up to 24 statements (the most recent).
updates = api.update(24)
if updates is not None:
    print(f"{ len(updates) } statements_downloaded")
api.history("monthly").tail()

# %% [markdown]
# # Plotting data

# %% [markdown]
# ## Monthly consumption history

# %%
df = api.history("monthly")

plt.figure()
plt.bar(df.index, df["Gas Consumption"], width=bin_width, alpha=alpha)
plt.xticks(rotation=90)
plt.title("Monthly Gas Consumption")
plt.ylabel("m$^3$")
os.makedirs("images", exist_ok=True)
plt.savefig(
    os.path.join("images", "monthly_gas_consumption.png"),
    bbox_inches=bbox_inches,
    transparent=transparent,
    facecolor=facecolor,
)

plt.figure()
plt.bar(df.index, df["Water Consumption"], width=bin_width, alpha=alpha)
plt.xticks(rotation=90)
plt.title("Monthly Water Consumption")
plt.ylabel("m$^3$")
plt.savefig(
    os.path.join("images", "monthly_water_consumption.png"),
    bbox_inches=bbox_inches,
    transparent=transparent,
    facecolor=facecolor,
)

# %% [markdown]
# ## Annual CO2 emissions

# %%
from utility_bill_scraper import GAS_KGCO2_PER_CUBIC_METER

df["kgCO2"] = df["Gas Consumption"] * GAS_KGCO2_PER_CUBIC_METER
df["year"] = [int(x[0:4]) for x in df.index]
df["month"] = [int(x[5:7]) for x in df.index]

plt.figure()
df.groupby("year").sum()["Gas Consumption"].plot.bar(width=bin_width, alpha=alpha)
plt.ylabel("m$^3$")
ylim = plt.ylim()
ax = plt.gca()
ax2 = ax.twinx()
plt.ylabel("tCO$_2$e")
plt.ylim([GAS_KGCO2_PER_CUBIC_METER * y / 1e3 for y in ylim])
plt.title("Annual CO$_2$e emissions from natural gas")
plt.savefig(
    os.path.join("images", "annual_co2_emissions_natural_gas.png"),
    bbox_inches=bbox_inches,
    transparent=transparent,
    facecolor=facecolor,
)

# %% [markdown]
# ## CO2 emissions vs previous year

# %%
n_years_history = 1

plt.figure()
for year, df_year in df.groupby("year"):
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
plt.savefig(
    os.path.join("images", "monthly_co2_emissions_natural_gas.png"),
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
            np.cumsum(df_year["Gas Consumption"]),
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
plt.title("Cumulative CO$_2$e emissions from natural gas per year")
plt.savefig(
    os.path.join("images", "cumulative_co2_emissions_natural_gas.png"),
    bbox_inches=bbox_inches,
    transparent=transparent,
    facecolor=facecolor,
)
