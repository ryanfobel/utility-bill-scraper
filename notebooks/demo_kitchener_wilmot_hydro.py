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

import subprocess
import os
from glob import glob

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import rcParams

# Add parent directory to python path.
import sys
sys.path.insert(0, '..')
from utility_bill_scraper import process_pdf, convert_data_to_df
import utility_bill_scraper.kitchener_wilmot_hydro as kwh

# %matplotlib inline

rcParams.update({
    'figure.figsize': (12, 6)
})

data_directory = os.path.abspath(os.path.join('..', 'data'))

# +
bills_list = glob(os.path.join(os.path.join('..', 'tests', kwh.get_name()), '*.pdf'))

data = []

print('Scrape data from the following pdf files:')
for pdf_file in bills_list:
    print('  %s' % pdf_file)
    result = process_pdf(pdf_file, rename=True)
    if result:
        data.append(result)

# Convert the list of dictionaries into a dictionary of data frames (one for
# each utility in the dataset).
df = convert_data_to_df(data)

# +
filepath = os.path.join(data_directory, kwh.get_name(), 'data.csv')

try:
    # Save the data to a csv file
    df_kwhydro = df[kwh.get_name()]
    
    # If the data directory doesn't exist yet, create it
    if not os.path.isdir(os.path.join(data_directory, kwh.get_name())):
        os.makedirs(os.path.join(data_directory, kwh.get_name()))
    
    df_kwhydro.to_csv(filepath)
except NameError:
    df_kwhydro = pd.read_csv(filepath).set_index('Date')

plt.figure()
df_kwhydro['Off Peak Consumption'].plot()
df_kwhydro['Mid Peak Consumption'].plot()
df_kwhydro['On Peak Consumption'].plot()
df_kwhydro['Total Consumption'].plot()
plt.ylim((0, None))
plt.title('Monthly Electricity Consumption')
plt.ylabel('kWh')
plt.legend(['Off Peak', 'Mid Peak', 'On Peak', 'Total'])

# Carbon intensity of electricity generation in Ontario (40-77 g CO2 / kWh)
# * 40 g / kWh (https://www.neb-one.gc.ca/nrg/sttstc/lctrct/rprt/
#               2017cndrnwblpwr/ghgmssn-eng.html)
# * 77 g / kWh (https://www.conferenceboard.ca/hcp/provincial/environment/
#               low-emitting-electricity-production.aspx)
# * This is likely to go up when Pickering is closed
#   https://www.opg.com/darlington-refurbishment/Documents/IntrinsikReport_GHG_OntarioPower.pdf

cabron_intensity_kgCO2_per_kwh = .077
print('annual electricity usage: %.1f kWh' % (
    df_kwhydro['Total Consumption'].iloc[-12:].sum()))
print('annual electricity cost: $%.2f' % (df_kwhydro['Amount Due'].iloc[-12:].sum()))
print('annual CO2 emissions from electricity: %.2f kg' % (
    df_kwhydro['Total Consumption'].iloc[-12:].sum() *
    cabron_intensity_kgCO2_per_kwh))
# -


