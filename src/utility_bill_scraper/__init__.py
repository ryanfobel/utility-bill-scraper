import datetime as dt
import glob
import io
import json
import os
import re
import shutil
import subprocess
import tempfile

import arrow
import pandas as pd
from apiclient import discovery
from google.oauth2.service_account import Credentials
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from selenium import webdriver

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Natural gas emission factor
# 119.58 lbs CO2/1000 cubic feet of natural gas
# 1.915 kg CO2/1 m^3 natural gas [119.58 lbs * (1 kg / 2.204623 lbs) *
#   (1 ft^3 / (0.0254 * 12)**3 m^3) / 1000]
GAS_KGCO2_PER_CUBIC_METER = (
    119.58 * (1 / 2.204623) * (1 / (0.0254 * 12) ** 3) / 1000
)  # kg CO2/1 m^3 natural gas

# Natural gas energy density
# 1,037 Btu / ft^3 (https://www.eia.gov/tools/faqs/faq.php?id=45&t=8)
# Energy per m^3: 1,037 Btu / ft^3 * 1055.1 J / 1 Btu * 1 ft^3 /
#   (0.0254 * 12)**3 m^3
#   37 MJ/m3 (https://hypertextbook.com/facts/2002/JanyTran.shtml)

GAS_JOULES_PER_CUBIC_METER = 1037 * 1055.1 / (0.0254 * 12) ** 3  # J / m^3
KWH_PER_JOULE = 1.0 / (60 * 60 * 1000)
GAS_KWH_PER_CUBIC_METER = GAS_JOULES_PER_CUBIC_METER * KWH_PER_JOULE


def is_number(s):
    """Returns True if string is a number."""
    return s.replace(".", "", 1).isdigit()


def format_fields(input_list):
    """Strip newlines and trailing colons from fields and convert numbers to
    floats."""
    fields = [x.strip().strip(":") for x in input_list if x.find("</br>") == -1]
    return [float(x) if is_number(x) else x for x in fields]


def convert_divs_to_df(divs):
    """Convert list of divs to a pandas DataFrame describing the position and
    geomtery of each tag."""
    pos_re = (
        r"left:(?P<left>\d+)px.*top:(?P<top>\d+)px.*"
        r"width:(?P<width>\d+)px.*height:(?P<height>\d+)"
    )

    df = pd.DataFrame()
    for x in divs:
        pos = re.search(pos_re, x.decode()).groupdict()
        try:
            df = df.append(
                pd.DataFrame(
                    dict(
                        left=int(pos["left"]),
                        top=int(pos["top"]),
                        width=int(pos["width"]),
                        height=int(pos["height"]),
                        fields=[format_fields(x.span.contents)],
                    )
                )
            )
        except AttributeError:
            pass

    df["right"] = df["left"] + df["width"]
    df["bottom"] = df["top"] + df["height"]
    return df


def is_kitchener_utilities_bill(soup):
    """Check if this is a Kitchener Utilities bill."""

    def find_kitchener_utilities(tag):
        return (
            tag.name == "span"
            and tag.decode().find("Supplier: KITCHENER UTILITIES") >= 0
        )

    return len(soup.find_all(find_kitchener_utilities)) > 0


def is_kitchener_wilmot_hydro_bill(soup):
    """Check if this is a Kitchener-Wilmot Hydro bill."""

    def find_kitchener_wilmot_hydro(tag):
        return (
            tag.name == "span" and tag.decode().find("KITCHENER-WILMOT HYDRO INC") >= 0
        )

    return len(soup.find_all(find_kitchener_wilmot_hydro)) > 0


def is_enbridge_gas_bill(soup):
    """Check if this is an Enbridge Gas bill."""

    def find_enbridge_gas(tag):
        return (
            tag.name == "span"
            and tag.decode().find("Enbridge Gas Distribution Inc.") >= 0
        )

    return len(soup.find_all(find_enbridge_gas)) > 0


def pdf_to_html(pdf_file):
    basename, ext = os.path.splitext(pdf_file)
    html_file = basename + ".html"

    # If we're in a conda environment, use the conda packaged pdf2txt.py
    if os.getenv("CONDA_PREFIX") and os.path.exists(
        os.path.join(os.getenv("CONDA_PREFIX"), "Scripts", "pdf2txt.py")
    ):
        subprocess.check_output(
            [
                "python",
                r"%CONDA_PREFIX%\Scripts\pdf2txt.py",
                "-o%s" % html_file,
                pdf_file,
            ],
            shell=True,
        )
    else:  # Otherwise use the pip version
        subprocess.check_output(
            ["pdf2txt.py '-o%s' '%s'" % (html_file, pdf_file)],
            shell=True,
        )

    return html_file

    """
    elif is_enbridge_gas_bill(soup):
        from . import enbridge as en

        summary = en.get_summary(soup)

        new_name = "%s - %s - $%s.pdf" % (
            arrow.get(summary["Bill Date"], "MMM DD, YYYY").format("YYYY-MM-DD"),
            en.get_name(),
            summary["Amount Due"],
        )

        result = {"name": en.get_name(), "summary": summary}
    elif is_kitchener_wilmot_hydro_bill(soup):
        from . import kitchener_wilmot_hydro as kwh

        date = kwh.get_billing_date(soup)
        amount_due = kwh.get_amount_due(soup)
        new_name = "%s - %s - $%.2f.pdf" % (date, kwh.get_name(), amount_due)

        result = {
            "name": kwh.get_name(),
            "date": date,
            "amount due": amount_due,
            "electricity rates": kwh.get_electricity_rates(soup),
            "electricity consumption": kwh.get_electricity_consumption(soup),
        }
    else:
        print("Unrecognized bill type.")
    """


def is_gdrive_path(path):
    if path:
        return path.startswith("https://drive.google.com/drive")
    else:
        return False


class Timeout(Exception):
    pass


class UnsupportedFileTye(Exception):
    pass


class GDriveHelper:
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


class UtilityAPI:
    def __init__(
        self,
        user=None,
        password=None,
        data_path=None,
        file_ext=".csv",
        headless=True,
        timeout=10,
        save_statements=True,
        google_sa_credentials=None,
    ):
        self._user = user
        self._password = password
        self._driver = None
        self._browser = None
        self._headless = headless
        self._temp_download_dir = tempfile.mkdtemp()
        self._data_path = data_path or os.path.abspath(os.path.join(".", "data"))
        self._file_ext = file_ext
        self._save_statements = save_statements

        if google_sa_credentials is not None:
            self._gdh = GDriveHelper(google_sa_credentials)
        else:
            self._gdh = None

        supported_filetypes = [".csv"]
        if self._file_ext not in supported_filetypes:
            raise UnsupportedFileTye(
                f"`file_ext`={self._file_ext} has an invalid filetype. Acceptable extensions are "
                f'{",".join([f"`{x}`" for x in supported_filetypes])}'
            )

        self._history = pd.DataFrame()

        # If `data_path` is a google drive folder download the data file.
        if is_gdrive_path(self._data_path):
            if google_sa_credentials is None:
                raise RuntimeError(
                    "`data_path` looks like a google drive folder, but `google_sa_credentials` is None."
                )

            folder_id = self._data_path.split("/")[-1]
            utility_folder = self._gdh.get_file_in_folder(folder_id, self.name)
            data_file = self._gdh.get_file_in_folder(
                utility_folder["id"], "data" + self._file_ext
            )
            self._gdh.download_file(
                data_file["id"],
                os.path.join(self._temp_download_dir, "data" + self._file_ext),
            )
            self._history = pd.read_csv(
                os.path.join(self._temp_download_dir, "data" + self._file_ext)
            ).set_index("Issue Date")
        elif os.path.exists(
            os.path.join(self._data_path, self.name, "data" + self._file_ext)
        ):
            # Load csv with previously cached data if it exists locally.
            self._history = pd.read_csv(
                os.path.join(self._data_path, self.name, "data" + self._file_ext)
            ).set_index("Issue Date")

        self._timeout = timeout

    def _init_driver(self, browser="Firefox"):
        self._browser = browser
        if self._browser == "Chrome":
            options = webdriver.ChromeOptions()
            prefs = {"download.default_directory": self._temp_download_dir}
            options.add_experimental_option("prefs", prefs)
            if self._headless:
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--headless")
                options.add_argument("--disable-gpu")
                options.add_argument(
                    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36"
                )
            self._driver = webdriver.Chrome(options=options)
        elif self._browser == "Firefox":
            options = webdriver.firefox.options.Options()
            options.set_preference("browser.download.folderList", 2)
            options.set_preference("browser.download.dir", self._temp_download_dir)
            options.set_preference("browser.download.useDownloadDir", True)
            options.set_preference(
                "browser.download.viewableInternally.enabledTypes", ""
            )
            options.set_preference(
                "browser.helperApps.neverAsk.saveToDisk",
                "application/pdf;text/plain;application/text;text/xml;application/xml",
            )
            options.set_preference("pdfjs.disabled", True)
            # disable the built-in PDF viewer
            if self._headless:
                options.add_argument("--headless")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--start-maximized")
                options.add_argument("--disable-gpu")
                options.add_argument("--no-sandbox")
            self._driver = webdriver.Firefox(options=options)

    def history(self):
        return self._history

    def __del__(self):
        if self._driver:
            self._close_driver()

    def _close_driver(self):
        self._driver.close()
        self._driver = None

    def update(self, max_downloads=None):
        # Download any new statements.
        start_date = None
        if len(self._history):
            start_date = (
                arrow.get(self._history.index[-1]).date() + dt.timedelta(days=1)
            ).isoformat()
        pdf_files = self.download_statements(
            start_date=start_date, max_downloads=max_downloads
        )

        if self._save_statements:
            # If `data_path` is a google drive url, upload pdfs to gdrive.
            if is_gdrive_path(self._data_path):
                folder_id = self._data_path.split("/")[-1]
                try:
                    utility_folder = self._gdh.get_file_in_folder(folder_id, self.name)
                except IndexError:
                    utility_folder = self._gdh.create_subfolder(folder_id, self.name)
                try:
                    statements_folder = self._gdh.get_file_in_folder(
                        utility_folder["id"], "statements"
                    )
                except IndexError:
                    statements_folder = self._gdh.create_subfolder(
                        utility_folder["id"], "statements"
                    )
                for local_path in pdf_files:
                    self._gdh.create_file_in_folder(statements_folder["id"], local_path)
            else:
                # If `data_path` is a local path, copy pdfs to their new location.
                os.makedirs(
                    os.path.join(self._data_path, self.name, "statements"),
                    exist_ok=True,
                )
                for local_path in pdf_files:
                    shutil.move(
                        local_path,
                        os.path.join(
                            self._data_path,
                            self.name,
                            "statements",
                            os.path.basename(local_path),
                        ),
                    )

                # Update the `pdf_files` list
                pdf_files = [
                    os.path.join(
                        self._data_path,
                        self.name,
                        "statements",
                        os.path.basename(local_path),
                    )
                    for local_path in pdf_files
                ]

        df_new_rows = pd.DataFrame()
        for pdf in pdf_files:
            df = self.scrape_pdf_file(pdf)
            if df is not None:
                df_new_rows = df_new_rows.append(df)
        self._history = self._history.append(df_new_rows)

        # Update history

        # If `data_path` is a google drive folder, upload the data file.
        if is_gdrive_path(self._data_path):
            folder_id = self._data_path.split("/")[-1]
            try:
                utility_folder = self._gdh.get_file_in_folder(folder_id, self.name)
            except IndexError:
                utility_folder = self._gdh.create_subfolder(folder_id, self.name)

            self._history.to_csv(
                os.path.join(self._temp_download_dir, "data" + self._file_ext)
            )

            try:
                data_file = self._gdh.get_file_in_folder(
                    utility_folder["id"], "data" + self._file_ext
                )
                self._gdh.upload_file(
                    data_file["id"],
                    os.path.join(self._temp_download_dir, "data" + self._file_ext),
                )
            except IndexError:
                data_file = self._gdh.create_file_in_folder(
                    utility_folder["id"],
                    os.path.join(self._temp_download_dir, "data" + self._file_ext),
                )

        else:
            # Create directories if necessary
            os.makedirs(os.path.join(self._data_path, self.name), exist_ok=True)

            # Update csv file
            self._history.to_csv(
                os.path.join(self._data_path, self.name, "data" + self._file_ext)
            )

        return df_new_rows

    def scrape_pdf_file(self, pdf_file):
        cached_invoice_dates = list(self._history.index)

        # Scrape data from pdf file
        date = os.path.splitext(os.path.basename(pdf_file))[0].split(" - ")[0]

        # If we've already scraped this pdf, continue
        if date not in cached_invoice_dates:
            print("Scrape data from %s" % pdf_file)
            try:
                result, new_name = self.extract_data(pdf_file)
                os.rename(pdf_file, os.path.join(os.path.dirname(pdf_file), new_name))
                return self.convert_data_to_df([result])
            except Exception as e:
                print(e)
        return None
