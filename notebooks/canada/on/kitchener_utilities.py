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

# %% [markdown] tags=[]
# [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ryanfobel/utility-bill-scraper/blob/main/notebooks%2Fcanada%2Fon%2Fkitchener_utilities.ipynb)
# [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/ryanfobel/utility-bill-scraper/main?labpath=notebooks%2Fcanada%2Fon%2Fkitchener_utilities.ipynb)
#
# # Introduction
#
# This notebook demonstrates downloading pdf statements and extracting data from a [Kitchener Utilities](https://www.kitchenerutilities.ca) account. You can launch an interactive version of this page by clicking on the badge at the top of the page.
#
# ## Setup
#
# Run all of the cells in the notebook (press `SHIFT`+`ENTER` to run each cell individually or run the entire notebook by selecting `Run`/`Run all cells` from the menu. After the notebook finishes running (~1-5 minutes), you'll be able to download your data as a `download.zip` file (containing both a summary `monthly.csv` and the `*.pdf` statements).This file should appear in the file browser on the left and you can download it by `Right-clicking` on it and clicking `Download`.

# %%
try:
    pass
except ModuleNotFoundError:
    import subprocess
    import sys

    cmd = (
        f"{sys.executable} -m pip install --force-reinstall "
        "git+https://github.com/ryanfobel/utility-bill-scraper.git@colab "
        "pandas==1.1.5"
    )
    subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode("utf-8")

from utility_bill_scraper import install_colab_dependencies

install_colab_dependencies(
    required_envs=["KITCHENER_UTILITIES_USER", "KITCHENER_UTILITIES_PASSWORD"]
)

# %matplotlib inline

import datetime as dt
import os
import shutil
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
# # CO2 emissions vs previous year

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

# %% [markdown]
# ## Save data as `downloads.zip` or print link to gdrive folder
#
# Generate a zip file with all of the data. `Right-click` on the file `downloads.zip` in the file browser on the left (it'll be in the `notebooks` folder). If `DATA_PATH` is a google drive link, print the url.

# %%
from utility_bill_scraper import is_gdrive_path

data_path = os.environ["DATA_PATH"]
if is_gdrive_path(data_path):
    print(data_path)
else:
    print(shutil.make_archive(os.path.join(".", "download"), "zip", data_path))
