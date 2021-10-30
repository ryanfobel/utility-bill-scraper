# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
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

# # Introduction
#
# This notebook demonstrates scraping of data from [Kitchener-Wilmot Hydro](https://www.kwhydro.on.ca) electricity bills.

# +
# %load_ext autoreload
# %autoreload 2

username = ""
password = ""

# Plotting preferences
bin_width = 0.9
alpha = 0.5
transparent = False
bbox_inches = "tight"
facecolor = "white"

# %matplotlib inline

import os
import shutil
import sys

# Update the path to include the src directory
sys.path.insert(0, os.path.abspath(os.path.join("..", "..", "..", "src")))

import matplotlib.pyplot as plt
from dotenv import load_dotenv
from matplotlib import rcParams

import utility_bill_scraper.canada.on.kitchener_wilmot_hydro as kwh

# Load the `.env` file into the environment if it exists
load_dotenv()

rcParams.update({"figure.figsize": (12, 6)})

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
    headless=False,
)

"""
# Get up to 24 statements (the most recent).
updates = api.update(1)
if updates is not None:
    print(f"{ len(updates) } statements_downloaded")
api.history().tail()
"""

# +

# api.download_statements(max_downloads=1)

import tempfile
import time

# +
import arrow

self = api
start_date = None
end_date = None

# def download_statements(self, start_date=None, end_date=None, timeout=5):
download_path = tempfile.mkdtemp()
self._init_driver()
downloaded_files = []

self._login()

# convert start and end dates to date objects
if start_date:
    start_date = arrow.get(start_date).date()
if end_date:
    end_date = arrow.get(end_date).date()

# Iterate through the invoices in reverse chronological order
# (i.e., newest invoices are first).

# +
link = self._driver.find_element_by_link_text("Bills & Payment")
link.location_once_scrolled_into_view
link.click()

self._driver.switch_to.frame("iframe-BILLINQ")
time.sleep(0.5)

# +
from utility_bill_scraper import wait_for_element


@wait_for_element
def get_bills_table():
    return self._driver.find_element_by_id("billsTable")


@wait_for_element
def get_bills_table_rows(bills_table):
    rows = [
        [y for y in x.find_elements_by_tag_name("td")]
        for x in bills_table.find_element_by_tag_name(
            "tbody"
        ).find_elements_by_tag_name("tr")[2:]
    ]
    return rows


bills_table = get_bills_table()
rows = get_bills_table_rows(bills_table)
# -

max_downloads = 1

data = []
for row in rows:
    row_data = [x.text for x in row[1:]]

    date = arrow.get(row_data[0], "MMM D, YYYY").date()

    data.append(row_data)
    new_filepath = os.path.join(
        download_path,
        "%s - %s - $%s.pdf" % (date.isoformat(), self.name, row_data[1].split(" ")[1]),
    )
    downloaded_files.append(new_filepath)

    # download the pdf invoice
    img = row[0].find_element_by_tag_name("img")
    filepath = self.download_link(img, "pdf")
    print(filepath, new_filepath)
    shutil.move(filepath, new_filepath)

downloaded_files
pdf = downloaded_files[0]
pdf

# +
result, new_name = api.extract_data(pdf)

print(result, new_name)

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
print(
    "annual electricity usage: %.1f kWh"
    % (df_kwh["Total Consumption"].iloc[-12:].sum())
)
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
