# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.3.3
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# # Introduction
#
# This notebook demonstrates scraping of data from [Kitchener-Wilmot Hydro](https://www.kwhydro.on.ca) electricity bills.

# +
# %load_ext autoreload
# %autoreload 2

import os

# Add parent directory to python path.
import sys
import time
from glob import glob

import arrow
import matplotlib.pyplot as plt
import pandas as pd
from IPython import display
from matplotlib import rcParams

sys.path.insert(0, "..")
import utility_bill_scraper.kitchener_wilmot_hydro as kwh
from utility_bill_scraper import convert_data_to_df, process_pdf

# %matplotlib inline

rcParams.update({"figure.figsize": (12, 6)})

data_directory = os.path.abspath(os.path.join("..", "data"))

# +
kwh_api = None

try:
    # Create a Kitchener-Wilmot Hydro API object with your user name and password
    from credentials import password, user

    kwh_api = kwh.KitchenerWilmotHydroAPI(user[kwh.get_name()], password[kwh.get_name()], data_directory)

    print("Downloading invoices from %s..." % kwh_api.name)
    start_time = time.time()
    invoices = kwh_api.download_invoices()
    print("kwh_api.download_invoices() took %d seconds" % (time.time() - start_time))
    display(invoices.head())
    bills_list = glob(os.path.join(kwh_api._invoice_directory, "*.pdf"))
except ModuleNotFoundError:
    print("Using test data...")
    bills_list = glob(os.path.join(os.path.join("..", "tests", kwh.get_name()), "*.pdf"))

# +
# Load csv with previously cached data if it exists
df_kwh = pd.DataFrame()
cached_invoice_dates = []
filepath = os.path.join(data_directory, kwh.get_name(), "data.csv")

if os.path.exists(filepath):
    df_kwh = pd.read_csv(filepath).set_index("Date")
    cached_invoice_dates = list(df_kwh.index)

# Scrape data from pdf files
data = []

for pdf_file in bills_list:
    date = os.path.splitext(os.path.basename(pdf_file))[0].split(" - ")[0]

    # If we've already scraped this pdf, continue
    if date not in cached_invoice_dates:
        print("Scrape data from %s" % pdf_file)
        result = process_pdf(pdf_file, rename=True)
        if result:
            data.append(result)

# Convert the list of dictionaries into a dictionary of data frames (one for
# each utility in the dataset).
df = convert_data_to_df(data)

# If there's any new data, append it to the cached data
if df:
    df_kwh = df_kwh.append(df[kwh.get_name()])

    # If the data directory doesn't exist yet, create it
    if not os.path.isdir(os.path.join(data_directory, kwh.get_name())):
        os.makedirs(os.path.join(data_directory, kwh.get_name()))

    # Update csv file
    df_kwh.to_csv(filepath)

# +
plt.figure()
df_kwh["Off Peak Consumption"].plot()
df_kwh["Mid Peak Consumption"].plot()
df_kwh["On Peak Consumption"].plot()
df_kwh["Total Consumption"].plot()
plt.ylim((0, None))
plt.title("Monthly Electricity Consumption")
plt.ylabel("kWh")
plt.legend(["Off Peak", "Mid Peak", "On Peak", "Total"])

# Carbon intensity of electricity generation in Ontario (40-77 g CO2 / kWh)
# * 40 g / kWh (https://www.neb-one.gc.ca/nrg/sttstc/lctrct/rprt/
#               2017cndrnwblpwr/ghgmssn-eng.html)
# * 77 g / kWh (https://www.conferenceboard.ca/hcp/provincial/environment/
#               low-emitting-electricity-production.aspx)
# * This is likely to go up when Pickering is closed
#   https://www.opg.com/darlington-refurbishment/Documents/IntrinsikReport_GHG_OntarioPower.pdf

cabron_intensity_kgCO2_per_kwh = 0.077
print("annual electricity usage: %.1f kWh" % (df_kwh["Total Consumption"].iloc[-12:].sum()))
print("annual electricity cost: $%.2f" % (df_kwh["Amount Due"].iloc[-12:].sum()))
print(
    "annual CO2 emissions from electricity: %.2f kg"
    % (df_kwh["Total Consumption"].iloc[-12:].sum() * cabron_intensity_kgCO2_per_kwh)
)
# -
if kwh_api:
    kwh_api.download_hourly_data()

    # Combine all data into a single dataframe
    files = glob(os.path.join(kwh_api._hourly_data_directory, "*.csv"))

    df = pd.read_csv(files[0], index_col=0)
    for f in files[1:]:
        df = df.append(pd.read_csv(f, index_col=0))

    # Plot daily use
    df["Date"] = [arrow.get(x).date().isoformat() for x in df.index]
    df_base = df.groupby("Date").sum()
    df_base["kWh"].plot()
    plt.title("Daily use")
    plt.ylabel("kWh")
