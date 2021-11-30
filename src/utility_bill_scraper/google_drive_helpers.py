import fnmatch
import json
import os
import io

from apiclient import discovery
from google.oauth2.service_account import Credentials
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class GoogleDriveHelper:
    def __init__(self, service_account_info):
        if type(service_account_info) == str:
            service_account_info = json.loads(service_account_info)
        self._credentials = Credentials.from_service_account_info(
            info=service_account_info,
            scopes=DEFAULT_SCOPES,
        )
        self._service = discovery.build("drive", "v3", credentials=self._credentials)

    def get_file_in_folder(self, folder_id, file_name):
        # Query the shared google folder for file that matches `file_name`
        return (
            self._service.files()
            .list(q=f"'{folder_id}' in parents and name='{file_name}'")
            .execute()["files"][0]
        )

    def get_files_in_folder(self, folder_id, pattern="*"):
        # Query the shared google folder for files that match `pattern`
        return [
            file
            for file in self._service.files()
            .list(q=f"'{folder_id}' in parents")
            .execute()["files"]
            if fnmatch.fnmatch(file["name"], pattern)
        ]

    def file_exists_in_folder(self, folder_id, file_name):
        try:
            self.get_file_in_folder(folder_id, file_name)
            return True
        except IndexError:
            return False

    def get_file(self, file_id):
        # Query google drive for a file matching the `file_id`
        return self._service.files().get(fileId=file_id).execute()

    def create_subfolder(self, parent_folder_id, name):
        file_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_folder_id],
        }
        file = self._service.files().create(body=file_metadata, fields="id").execute()
        return file

    def create_file_in_folder(self, folder_id, local_path):
        print(
            f"Upload file to google drive folder(folder_id={folder_id}, local_path={local_path}"
        )
        file_metadata = {"name": os.path.basename(local_path), "parents": [folder_id]}
        media = MediaFileUpload(local_path, mimetype="text/csv", resumable=True)
        file = (
            self._service.files()
            .create(body=file_metadata, media_body=media, fields="id")
            .execute()
        )
        return file

    def upload_file(self, file_id, local_path):
        print(f"Upload file to google drive(file_id={file_id}, local_path={local_path}")
        file = self.get_file(file_id)
        media_body = MediaFileUpload(
            local_path, mimetype=file["mimeType"], resumable=True
        )
        updated_file = (
            self._service.files()
            .update(fileId=file["id"], media_body=media_body)
            .execute()
        )
        return updated_file

    def download_file(self, file_id, local_path):
        print(
            f"Download file from google drive(file_id={file_id}, local_path={local_path}"
        )
        file = self._service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, file)
        done = False
        while done is False:
            status, done = downloader.next_chunk()

        # Make parent dirs if necessary.
        os.makedirs(os.path.split(local_path)[0], exist_ok=True)

        # Write the file.
        with open(local_path, "wb") as f:
            f.write(fh.getbuffer().tobytes())
