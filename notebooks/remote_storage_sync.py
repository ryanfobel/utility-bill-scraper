# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.13.0
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Load/save files in a shared Google Drive folder
#
# This notebook demonstrates how to work with files in a shared Google Drive folder

# %%
# %load_ext autoreload
# %autoreload 2

import os
import sys
import time
import datetime
import random
import tempfile

import pandas as pd

sys.path.insert(0, os.path.join("..", "src"))

from utility_bill_scraper import GDriveHelper

# %%
gd = GDriveHelper()

# List all spreadsheet files accessible by the service account.
gd._gc.list_spreadsheet_files()

# %% [markdown]
# # Setup the Google Drive folder
#
# Create a new folder in your Google Drive (e.g., "Mango Logs"). Copy the folder ID from the URL `https://drive.google.com/drive/u/0/folders/{FOLDER_ID_STRING}`
# and share it with the email address stored in your credentials file (printed by the next cell).

# %%
gd._gc.session.credentials.service_account_email

# %%
# Set the folder ID here
folder_id = '13ai3ELMsIrhjFGcv2Lqbwzb4sGkEWK-Y'

history_path = f'https://drive.google.com/drive/u/0/folders/{ folder_id }'
temp_download_dir = tempfile.mkdtemp()

"""
history_path = os.path.abspath(
    os.path.join(".", "data", name, "data.csv")
)
"""

name = 'Kitchener Utilities'

utility_folder = gd.get_file_in_folder(folder_id, name)
data_file = gd.get_file_in_folder(utility_folder['id'], 'data.csv')
gd.download_file(data_file['id'], os.path.join(temp_download_dir, 'data.csv'))
df = pd.read_csv(os.path.join(temp_download_dir, 'data.csv'))
df.head()

# %%
# Make some changes and save them locally at `{temp_download_dir}/data.csv`.

# ...

# Upload to google drive, replacing the original file.
gd.upload_file(data_file['id'], os.path.join(temp_download_dir, 'data.csv'))
