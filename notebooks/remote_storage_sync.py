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
import time
import datetime
import random

import pandas as pd
import gspread
from apiclient import discovery

# Authenticate with the service account
gc = gspread.service_account()
drive_service = discovery.build('drive', 'v3', credentials=gc.session.credentials)

# List all spreadsheet files accessible by the service account.
gc.list_spreadsheet_files()

# %% [markdown]
# # Setup the Google Drive folder
#
# Create a new folder in your Google Drive (e.g., "Mango Logs"). Copy the folder ID from the URL `https://drive.google.com/drive/u/0/folders/{FOLDER_ID_STRING}`
# and share it with the email address stored in your credentials file (printed by the next cell).

# %%
gc.session.credentials.service_account_email

# %%
import os
import io
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

# Set the folder ID here
folder_id = '13ai3ELMsIrhjFGcv2Lqbwzb4sGkEWK-Y'


def get_file_in_folder(folder_id, file_name):
    # Query the shared google folder for file that matches `file_name`
    return drive_service.files().list(q=f"'{folder_id}' in parents and name='{file_name}'").execute()['files'][0]

def get_file(file_id):
    # Query google drive for a file matching the `file_id`
    return drive_service.files().get(fileId=file_id).execute()

def upload_file(file_id, local_path):
    file = get_file(file_id)
    media_body = MediaFileUpload(local_path, mimetype=file['mimeType'], resumable=True)
    updated_file = drive_service.files().update(
            fileId=file['id'],
            media_body=media_body).execute()
    return updated_file

def download_file(file_id, local_path):
    file = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, file)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        print("Download %d%%." % int(status.progress() * 100))

    # Make parent dirs if necessary.
    os.makedirs(os.path.split(local_path)[0], exist_ok=True)

    # Write the file.
    with open(local_path, 'w') as f:
        f.write(fh.getvalue().decode('utf-8'))


# %%
name = 'Kitchener Utilities'
history_path = os.path.abspath(
    os.path.join(".", "data", name, "data.csv")
)

utility_folder = get_file_in_folder(folder_id, name)
data_file = get_file_in_folder(utility_folder['id'], 'data.csv')
download_file(data_file['id'], history_path)
df = pd.read_csv(history_path)
df.head()

# %%
# Make some changes and save them locally at `history_path`.

# ...

# Upload to google drive, replacing the original file.
upload_file(data_file['id'], history_path)

# %%
