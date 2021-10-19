import os
import re
import subprocess
import tempfile
import io
import glob
import shutil
import datetime as dt

import arrow
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
import gspread
from apiclient import discovery
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload


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
            tag.name == u"span"
            and tag.decode().find("Supplier: KITCHENER UTILITIES") >= 0
        )

    return len(soup.find_all(find_kitchener_utilities)) > 0


def is_kitchener_wilmot_hydro_bill(soup):
    """Check if this is a Kitchener-Wilmot Hydro bill."""

    def find_kitchener_wilmot_hydro(tag):
        return (
            tag.name == u"span" and tag.decode().find("KITCHENER-WILMOT HYDRO INC") >= 0
        )

    return len(soup.find_all(find_kitchener_wilmot_hydro)) > 0


def is_enbridge_gas_bill(soup):
    """Check if this is an Enbridge Gas bill."""

    def find_enbridge_gas(tag):
        return (
            tag.name == u"span"
            and tag.decode().find("Enbridge Gas Distribution Inc.") >= 0
        )

    return len(soup.find_all(find_enbridge_gas)) > 0


def process_pdf(pdf_file, rename=False, keep_html=False):
    """Extract data from a pdf file and return a nested Python dictionary.
    Optionally rename the pdf with the format:
        YYYY-MM-DD-UTILITY_NAME-$XX.xx.pdf
    If the `keep_html` flag is True, the intermediate html fill will be
    maintained."""
    basename, ext = os.path.splitext(pdf_file)
    basepath = os.path.dirname(pdf_file)
    html_file = basename + ".html"
    subprocess.check_output(
        ["python", r"%CONDA_PREFIX%\Scripts\pdf2txt.py", "-o%s" % html_file, pdf_file],
        shell=True,
    )

    with open(html_file, "r", encoding="utf8") as f:
        soup = BeautifulSoup(f, "html.parser")

    if keep_html:
        # re-write formatted html (useful for debugging)
        with open(html_file, "w", encoding="utf8") as f:
            f.write(str(soup.prettify().encode("utf-8")))
    else:
        os.remove(html_file)

    result = None
    new_name = None

    if is_kitchener_utilities_bill(soup):
        from . import kitchener_utilities as ku

        summary = ku.get_summary(soup)

        if "Pre-authorized Withdrawal" in summary.keys():
            amount_due = summary["Pre-authorized Withdrawal"]
        elif "Total Due" in summary.keys():
            amount_due = summary["Total Due"]
        else:
            print("Couldn't find amount due!")
            amount_due = None

        new_name = "%s - %s - $%.2f.pdf" % (
            arrow.get(summary["Issue Date"], "MMM DD YYYY").format("YYYY-MM-DD"),
            ku.get_name(),
            amount_due,
        )

        # To do: several functions were broken when updating to python3
        result = {
            "name": ku.get_name(),
            "summary": summary,
            "water consumption": ku.get_water_consumption(soup),
            # 'water and sewer charges': ku.get_water_and_sewer_charges(soup),
            "gas consumption": ku.get_gas_consumption(soup),
            # 'gas charges': ku.get_gas_charges(soup),
            # 'gas rates': ku.get_gas_rates(soup)
        }
    elif is_enbridge_gas_bill(soup):
        from . import enbridge as en

        summary = en.get_summary(soup)

        new_name = "%s - %s - $%s.pdf" % (
            arrow.get(summary[u"Bill Date"], "MMM DD, YYYY").format("YYYY-MM-DD"),
            en.get_name(),
            summary[u"Amount Due"],
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

    if rename and new_name:
        os.rename(pdf_file, os.path.join(basepath, new_name))

    return result


def convert_data_to_df(data):
    """Convert the list of dictionaries (returned from `process_pdf`) into a
    dictionary of pandas DataFrames keyed by utility name."""
    result = {}

    for x in data:
        if x["name"] not in result.keys():
            result[x["name"]] = pd.DataFrame()
        if x["name"] == "Kitchener Utilities":
            from . import kitchener_utilities as ku

            df = ku.convert_data_to_df([x])
        elif x["name"] == "Enbridge":
            from . import enbridge as en

            df = en.convert_data_to_df([x])
        elif x["name"] == "Kitchener-Wilmot Hydro":
            from . import kitchener_wilmot_hydro as kwh

            df = kwh.convert_data_to_df([x])
        else:
            print("Unknown name.")
            continue
        result[x["name"]] = result[x["name"]].append(df)

    return result


def is_gdrive_path(path):
    return path.startswith("https://drive.google.com/drive")


class Timeout(Exception):
    pass


class UnsupportedFileTye(Exception):
    pass


class GDriveHelper:
    def __init__(self):
        self._gc = gspread.service_account()
        self._service = discovery.build('drive', 'v3', credentials=self._gc.session.credentials)

    def get_file_in_folder(self, folder_id, file_name):
        # Query the shared google folder for file that matches `file_name`
        return self._service.files().list(q=f"'{folder_id}' in parents and name='{file_name}'").execute()['files'][0]

    def get_file(self, file_id):
        # Query google drive for a file matching the `file_id`
        return self._service.files().get(fileId=file_id).execute()

    def create_file_in_folder(self, folder_id, local_path):
        print(f"Upload file to google drive folder(folder_id={folder_id}, local_path={local_path}")
        file_metadata = {
            'name': os.path.basename(local_path),
            'parents': [folder_id]
        }
        media = MediaFileUpload(local_path, mimetype='text/csv', resumable=True)
        file = self._service.files().create(body=file_metadata,
            media_body=media,
            fields='id').execute()
        return file

    def upload_file(self, file_id, local_path):
        print(f"Upload file to google drive(file_id={file_id}, local_path={local_path}")
        file = self.get_file(file_id)
        media_body = MediaFileUpload(local_path, mimetype=file['mimeType'], resumable=True)
        updated_file = self._service.files().update(
                fileId=file['id'],
                media_body=media_body).execute()
        return updated_file

    def download_file(self, file_id, local_path):
        print(f"Download file from google drive(file_id={file_id}, local_path={local_path}")
        file = self._service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, file)
        done = False
        while done is False:
            status, done = downloader.next_chunk()

        # Make parent dirs if necessary.
        os.makedirs(os.path.split(local_path)[0], exist_ok=True)

        # Write the file.
        with open(local_path, 'wb') as f:
            f.write(fh.getbuffer().tobytes())


class UtilityAPI:

    def __init__(
        self,
        user=None,
        password=None,
        history_path=None,
        statement_path=None,
        file_ext='.csv',
        headless=True,
        timeout=10,
    ):
        self._user = user
        self._password = password
        self._driver = None
        self._browser = None
        self._headless = headless
        self._temp_download_dir = tempfile.mkdtemp()
        self._history_path = history_path or os.path.abspath(
            os.path.join(".", "data", self.name, "data" + file_ext)
        )
        self._file_ext = file_ext
        self._gdh = None

        supported_filetypes = [".csv"]
        if self._file_ext not in supported_filetypes:
            raise UnsupportedFileTye(
                "`file_ext` has an invalid filetype. Acceptable extensions are "
                f'{",".join([f"`{x}`" for x in supported_filetypes])}'
            )

        # If `history_path` is a google drive folder, initialize a
        # GDriveHelper object and download the data file.
        if is_gdrive_path(self._history_path):
            self._gdh = GDriveHelper()
            folder_id = self._history_path.split('/')[-1]
            utility_folder = self._gdh.get_file_in_folder(folder_id, self.name)
            data_file = self._gdh.get_file_in_folder(utility_folder['id'], 'data' + self._file_ext)
            self._gdh.download_file(data_file['id'], os.path.join(self._temp_download_dir,  'data' + self._file_ext))
            self._history = pd.read_csv(os.path.join(self._temp_download_dir, 'data' + self._file_ext)).set_index("Issue Date")
        elif os.path.exists(self._history_path):
            # Load csv with previously cached data if it exists locally.
            self._history = pd.read_csv(history_path).set_index("Issue Date")
        else:
            self._history = pd.DataFrame()

        self._statement_path = statement_path or os.path.abspath(
            os.path.join(".", "data", self.name, "statements")
        )

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
            start_date = (arrow.get(self._history.index[-1]).date() + dt.timedelta(days=1)).isoformat()
        pdf_files = self.download_statements(
            start_date=start_date, max_downloads=max_downloads
        )

        # If `statement_path` is a google drive url, upload pdfs to gdrive.
        if is_gdrive_path(self._statement_path):
            folder_id = self._statement_path.split('/')[-1]
            for local_path in pdf_files:
                if not self._gdh:
                    self._gdh = GDriveHelper()
                self._gdh.create_file_in_folder(folder_id, local_path)
        else:
            # If `statement_path` is a local path, copy pdfs to their new location.
            os.makedirs(self._statement_path, exist_ok=True)
            for local_path in pdf_files:
                shutil.move(local_path, os.path.join(self._statement_path, os.path.basename(local_path)))

            # Update the `pdf_files` list
            pdf_files = [os.path.join(self._statement_path, os.path.basename(local_path)) for file in pdf_files]
        return self._scrape_pdf_files(pdf_files)

    def _scrape_pdf_files(self, pdf_files=[]):
        cached_invoice_dates = list(self._history.index)

        # Scrape data from pdf files
        data = []
        for pdf_file in pdf_files:
            date = os.path.splitext(os.path.basename(pdf_file))[0].split(" - ")[0]

            # If we've already scraped this pdf, continue
            if date not in cached_invoice_dates:
                print("Scrape data from %s" % pdf_file)
                try:
                    result = process_pdf(pdf_file, rename=True)
                    if result:
                        data.append(result)
                except Exception as e:
                    print(e)

        # Convert the to a dataframe
        if len(data):
            df = self.convert_data_to_df(data)
            self._history = self._history.append(df)

            # Update history

            # If `history_path` is a google drive folder, initialize a
            # GDriveHelper object and download the data file.
            if is_gdrive_path(self._history_path):
                folder_id = self._history_path.split('/')[-1]
                utility_folder = self._gdh.get_file_in_folder(folder_id, self.name)
                data_file = self._gdh.get_file_in_folder(utility_folder['id'], 'data' + self._file_ext)
                self._history.to_csv(os.path.join(self._temp_download_dir, 'data' + self._file_ext))
                self._gdh.upload_file(data_file['id'], os.path.join(self._temp_download_dir, 'data' + self._file_ext))
            else:
                # If the parent directory of the history_path doesn't exist, create it.
                history_parent = os.path.abspath(
                    os.path.join(self._history_path, os.path.pardir)
                )
                if not os.path.exists(history_parent):
                    os.makedirs(history_parent)

                # Update csv file
                self._history.to_csv(self._history_path)

            return df


    from ._version import get_versions

    __version__ = get_versions()["version"]
    del get_versions
