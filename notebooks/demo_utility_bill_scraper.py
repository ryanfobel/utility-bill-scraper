# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.3'
#       jupytext_version: 0.8.6
#   kernelspec:
#     display_name: Python 2
#     language: python
#     name: python2
# ---

# # Introduction
#
# This notebook demonstrates scraping of data from a series of utility bills
# (pdfs). Currently, this library supports:
#
# * [Kitchener Utilities (gas & water)](https://www.kitchenerutilities.ca)
# * [Kitchener-Wilmot Hydro (electricity)](https://www.kwhydro.on.ca)

# +
# %load_ext autoreload
# %autoreload 2

import subprocess
import os
from glob import glob

import matplotlib.pyplot as plt
from matplotlib import rcParams

# Add parent directory to python path.
import sys
sys.path.insert(0, '..')
from utility_bill_scraper import process_pdf, convert_data_to_df

# %matplotlib inline

rcParams.update({
    'figure.figsize': (12, 6)
})

bills_list = glob(os.path.join(os.path.join('..', 'tests', '*'), '*.pdf'))

data = []

print('Scrape data from the following pdf files:')
for pdf_file in bills_list:
    print('  %s' % pdf_file)
    result = process_pdf(pdf_file)
    if result:
        data.append(result)

# Convert the list of dictionaries into a dictionary of data frames (one for
# each utility in the dataset).
df = convert_data_to_df(data)
# -

# # Gas and Water

# +
df_gas = df['Kitchener Utilities']

plt.figure()
df_gas['Gas & Water Charges'].plot()
plt.title('Gas & Water Charges')
plt.ylabel('\$')

plt.figure()
df_gas['Gas Consumption'].plot()
plt.title('Gas Consumption')
plt.ylabel('m$^3$')

plt.figure()
df_gas['Water Consumption'].plot()
plt.title('Water Consumption')
plt.ylabel('m$^3$')

df_gas.to_csv('Kitchener Utilities data.csv')

# Natural gas emission factor
# 119.58 lbs CO2/1000 cubic feet of natural gas
# 1.915 kg CO2/1 m^3 natural gas [119.58 lbs * (1 kg / 2.204623 lbs) *
#   (1 ft^3 / (0.0254 * 12)**3 m^3) / 1000]
kgCO2_per_cubic_meter = 119.58 * (1 / 2.204623) * \
    (1 / (0.0254 * 12)**3) / 1000  # kg CO2/1 m^3 natural gas

gas_variable_rate = 0.068371 + 0.135000  # $ / m^3

# Natural gas energy density
# 1,037 Btu / ft^3 (https://www.eia.gov/tools/faqs/faq.php?id=45&t=8)
# Energy per m^3: 1,037 Btu / ft^3 * 1055.1 J / 1 Btu * 1 ft^3 /
#   (0.0254 * 12)**3 m^3
#   37 MJ/m3 (https://hypertextbook.com/facts/2002/JanyTran.shtml)

joules_per_cubic_meter = 1037 * 1055.1 / (0.0254 * 12)**3  # J / m^3
kwh_per_joule = 1.0 / (60 * 60 * 1000)
kwh_per_cubic_meter = joules_per_cubic_meter * kwh_per_joule

# Energy use
energy_use_joules = df_gas['Gas Consumption'].sum() * joules_per_cubic_meter
energy_use_kwh = df_gas['Gas Consumption'].sum() * kwh_per_cubic_meter

furnace_efficiency = 0.95

print('annual gas usage: %.1f m^3' % (df_gas['Gas Consumption'].sum()))
print('annual heating energy usage: %.1f GJ (%.1f kWh)' % (
    energy_use_joules / 1e9, energy_use_kwh))
print('carbon intensity (heating): %d g CO2 / kWh' % (
    kgCO2_per_cubic_meter / kwh_per_cubic_meter * 1000))
print('heating energy per m^3 natural gas (%d%% efficient furnace):'
      ' %.2f kWh / m^3' % (
          100 * furnace_efficiency, furnace_efficiency * kwh_per_cubic_meter))
print('gas heating cost: $%.3f / kWh' % (
    gas_variable_rate / kwh_per_cubic_meter))
print('annual CO2 emissions from natural gas: %.1f kg' % (
    df_gas['Gas Consumption'].sum() * kgCO2_per_cubic_meter))
print('annual cost for natural gas: $%.2f' % (
    df_gas['Gas Consumption'].sum() * gas_variable_rate))

df_gas
# -

# # Electricity

# +
df_electricity = df['Kitchener-Wilmot Hydro']

plt.figure()
df_electricity['Off Peak Consumption'].plot()
df_electricity['Mid Peak Consumption'].plot()
df_electricity['On Peak Consumption'].plot()
df_electricity['Total Consumption'].plot()
plt.ylim((0, None))
plt.title('Monthly Electricity Consumption')
plt.ylabel('kWh')
plt.legend(['Off Peak', 'Mid Peak', 'On Peak', 'Total'])

df_electricity.to_csv('Kitchener-Wilmot Hydro data.csv')

# Carbon intensity of electricity generation in Ontario (40-77 g CO2 / kWh)
# * 40 g / kWh (https://www.neb-one.gc.ca/nrg/sttstc/lctrct/rprt/
#               2017cndrnwblpwr/ghgmssn-eng.html)
# * 77 g / kWh (https://www.conferenceboard.ca/hcp/provincial/environment/
#               low-emitting-electricity-production.aspx)
# * This is likely to go up when Pickering is closed
#   https://www.opg.com/darlington-refurbishment/Documents/IntrinsikReport_GHG_OntarioPower.pdf

cabron_intensity_kgCO2_per_kwh = .077
print('annual electricity usage: %.1f kWh' % (
    df_electricity['Total Consumption'].sum()))
print('annual electricity cost: $%.2f' % (df_electricity['Amount Due'].sum()))
print('annual CO2 emissions from electricity: %.2f kg' % (
    df_electricity['Total Consumption'].sum() *
    cabron_intensity_kgCO2_per_kwh))

df_electricity
# -

# # Monthly usage and offsetting
#
# Calculate average monthly usage and costs for offsetting with
# [Bullfrog Power](https://www.bullfrogpower.com).

# +
print('monthly electricity usage: %.1f kWh (avg), %.1f kWh (max)' % (
    df_electricity['Total Consumption'].mean(),
    df_electricity['Total Consumption'].max()))

print('monthly gas usage: %.1f m^3 (avg), %.1f m^3 (max)' % (
    df_gas['Gas Consumption'].mean(), df_gas['Gas Consumption'].max()))

print('\nmonthly electricity offset: $%.2f' % (
    df_electricity['Total Consumption'].mean() * 0.025))
print('monthly gas offset: $%.2f' % (
    df_gas['Gas Consumption'].mean() * 0.15))
print('total monthly offset: $%.2f' % (
    df_electricity['Total Consumption'].mean() * 0.025 +
    df_gas['Gas Consumption'].mean() * 0.15))
