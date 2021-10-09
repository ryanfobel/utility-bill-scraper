# ---
# jupyter:
#   jupytext:
#     formats: py:light,ipynb
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
# This notebook demonstrates scraping of data from the [Kitchener Utilities](https://www.kitchenerutilities.ca) website and gas & water bills (pdfs).
#
# ## Setup instructions: 
#
# 1. Create a new conda environment including all the requirements:
#
# ```sh
# conda create -n utility-bill-scraper numpy pandas jupyter arrow selenium
# activate utility-bill-scraper
#
# ```
#
# 2. Download [chromedriver](https://sites.google.com/a/chromium.org/chromedriver/downloads) and put it somewhere on your path.
#
# 3. Save your login credentials, to a file by uncommenting, editing the `user` and `password` variables, and running the cell below to write a `credentials.py` file.

"""
user = 'user'
password = 'password'

with open('credentials.py', 'w') as f:
    f.write("user = {'Kitchener Utilities': '%s'}\n" % user)
    f.write("password = {'Kitchener Utilities': '%s'}\n" % password)
"""

# +
# %load_ext autoreload
# %autoreload 2

import subprocess
import os
from glob import glob
import time

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import rcParams
from IPython import display

# Add parent directory to python path.
import sys
sys.path.insert(0, '..')
from utility_bill_scraper import process_pdf, convert_data_to_df
import utility_bill_scraper.kitchener_utilities as ku

# %matplotlib inline

rcParams.update({
    'figure.figsize': (12, 6)
})

data_directory = os.path.abspath(os.path.join('..', 'data'))
# -

ku_api = None
try:
    # Create a Kitchener Utilities API object with your user name and password
    from credentials import user, password

    ku_api = ku.KitchenerUtilitiesAPI(user[ku.get_name()],
                                      password[ku.get_name()],
                                      data_directory)

    print('Downloading invoices from %s...' % ku_api.name)
    start_time = time.time()
    invoices = ku_api.download_invoices()
    print('ku_api.download_invoices() took %d seconds' % (time.time() - start_time))
    display(invoices.head())
    bills_list = glob(os.path.join(ku_api._invoice_directory, '*.pdf'))
except ModuleNotFoundError:
    print('Using test data...')
    bills_list = glob(os.path.join(os.path.join('..', 'tests', ku.get_name()), '*.pdf'))

# +
# Load csv with previously cached data if it exists
df_ku = pd.DataFrame()
cached_invoice_dates = []
filepath = os.path.join(data_directory, ku.get_name(), 'data.csv')

if os.path.exists(filepath):
    df_ku = pd.read_csv(filepath).set_index('Issue Date')
    cached_invoice_dates = list(df_ku.index)

# Scrape data from pdf files
data = []

for pdf_file in bills_list:
    date = os.path.splitext(os.path.basename(pdf_file))[0].split(' - ')[0]
    
    # If we've already scraped this pdf, continue
    if date not in cached_invoice_dates:
        print('Scrape data from %s' % pdf_file)
        result = process_pdf(pdf_file, rename=True)
        if result:
            data.append(result)

# Convert the list of dictionaries into a dictionary of data frames (one for
# each utility in the dataset).
df = convert_data_to_df(data)

# If there's any new data, append it to the cached data
if df:
    df_ku = df_ku.append(df[ku.get_name()])
    
    # If the data directory doesn't exist yet, create it
    if not os.path.isdir(os.path.join(data_directory, ku.get_name())):
        os.makedirs(os.path.join(data_directory, ku.get_name()))

    # Update csv file
    df_ku.to_csv(filepath)

# +
plt.figure()
plt.bar(df_ku.index, df_ku['Gas Consumption'], width=0.9)
plt.xticks(rotation=90)
plt.title('Gas Consumption')
plt.ylabel('m$^3$')

plt.figure()
plt.bar(df_ku.index, df_ku['Water Consumption'], width=0.9)
plt.xticks(rotation=90)
plt.title('Water Consumption')
plt.ylabel('m$^3$')

df_ku.head()
# -

# If we have a handle to the API, we can also get consumption history from the website
if ku_api:
    df = pd.DataFrame({
        'Gas Consumption': ku_api.get_consumption_history('Gas'),
        'Water Consumption': ku_api.get_consumption_history('Water & Sewer')
    })
    display(df.head())


