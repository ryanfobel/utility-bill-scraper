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
# This notebook demonstrates scraping of data from [Enbridge](https://enbridgegas.com) gas bills.

# +
# %load_ext autoreload
# %autoreload 2

import os

# Add parent directory to python path.
import sys
from glob import glob

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import rcParams

sys.path.insert(0, "..")
from utility_bill_scraper import convert_data_to_df, process_pdf

# %matplotlib inline

rcParams.update({"figure.figsize": (12, 6)})

# +
bills_list = glob(os.path.join(os.path.join("..", "tests", "enbridge"), "*.pdf"))

data = []

print("Scrape data from the following pdf files:")
for pdf_file in bills_list:
    print("  %s" % pdf_file)
    result = process_pdf(pdf_file, rename=True)
    if result:
        data.append(result)

# Convert the list of dictionaries into a dictionary of data frames (one for
# each utility in the dataset).
df = convert_data_to_df(data)

# +
try:
    # Save the data to a csv file
    df_enbridge = df["Enbridge"]
    df_enbridge.to_csv("Enbridge data.csv")
except NameError:
    df_enbridge = pd.read_csv("Enbridge data.csv").set_index("Bill Date")

plt.figure()
df_enbridge["Adjusted volume"].plot()
plt.title("Gas Consumption")
plt.ylabel("m$^3$")
# -

df_enbridge
