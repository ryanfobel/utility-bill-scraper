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

# %%
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

api.history("monthly").tail()

# %%
import glob
import pandas as pd
import arrow

if api:
    api.download_hourly_data()

    # Combine all data into a single dataframe
    files = glob.glob(os.path.join(api._hourly_data_directory, "*.csv"))

    df = pd.read_csv(files[0], index_col=0)
    for f in files[1:]:
        df = df.append(pd.read_csv(f, index_col=0))

    # Plot hourly use over the past week
    plt.figure()
    days = 7
    df.iloc[-24*days:]["kWh"].plot.bar(width=1)
    plt.title("Hourly use over past week")
    plt.ylabel("kWh")
    plt.xticks(rotation=90)
    ticks, labels = plt.xticks()
    import math
    n = math.floor(len(ticks) / days)
    plt.xticks(ticks[1::n], [label.get_text().split(" ")[0] for label in labels[1::n]])

    # Plot daily use
    plt.figure()
    df["Date"] = [arrow.get(x).date().isoformat() for x in df.index]
    df_base = df.groupby("Date").sum()
    df_base["kWh"].plot()
    plt.title("Daily use")
    plt.ylabel("kWh")
    plt.xticks(rotation=90)
