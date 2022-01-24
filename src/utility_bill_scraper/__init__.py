import datetime as dt
import errno
import functools
import getpass
import glob
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from functools import wraps

import arrow
import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
)

from .google_drive_helpers import GoogleDriveHelper

LIGHT_COLORMAP = [
    (0.533, 0.741, 0.902),
    (0.984, 0.698, 0.345),
    (0.565, 0.804, 0.592),
    (0.965, 0.667, 0.788),
    (0.749, 0.647, 0.329),
    (0.737, 0.6, 0.78),
    (0.929, 0.867, 0.275),
    (0.941, 0.494, 0.431),
    (0.549, 0.549, 0.549),
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


def is_gdrive_path(path):
    if path:
        return path.startswith("https://drive.google.com/drive")
    else:
        return False


def wait_for_element(func, seconds=5, *args, **kwargs):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        t_start = time.time()
        while time.time() - t_start < seconds:
            try:
                return func(*args, **kwargs)
            except NoSuchElementException:
                pass
        raise Timeout

    return wrapper


def _run_cmd(cmd):
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True).decode(
        "utf-8"
    )


def install_colab_dependencies(required_envs, debug=False):
    """Detect if we are running in a colab environment, and if so, install
    necessary dependencies.

    required_envs: list of environnment variable names require to run the
        notebook. These will be loaded from a `.env` file in the user's google
        drive if available; otherwise, the user will be propted for values, and
        they will be saved to a `.env` file for future use.
    """
    if "google.colab" in sys.modules.keys():
        output = ""
        if not os.path.exists("/usr/bin/chromedriver"):
            output += _run_cmd(f"apt-get update")
            output += _run_cmd(f"apt install chromium-chromedriver")

        if debug:
            print(output)

        # mount the user's google drive
        from google.colab import drive

        drive.mount("/content/drive")

        os.environ["DATA_PATH"] = "/content/drive/MyDrive/Colab Notebooks/data"
        os.environ["BROWSER"] = "Chrome"
        dot_env_path = os.path.join(os.environ["DATA_PATH"], ".env")

        from dotenv import load_dotenv

        load_dotenv(dot_env_path)

        def get_env(env_name):
            """Check if the environment variable exists; otherwise prompt the
            user and append it to the `.env` file."""

            if not os.getenv(env_name):
                print(f"Enter a value for { env_name }")
                if "PASSWORD" in env_name.upper():
                    value = getpass.getpass()
                else:
                    value = input()
                with open(dot_env_path, "a") as f:
                    f.write(f"{ env_name }={ value }\n")
                os.environ[env_name] = value

        for name in required_envs:
            get_env(name)


def wait_for_permission(func, seconds=5, *args, **kwargs):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        t_start = time.time()
        while time.time() - t_start < seconds:
            try:
                return func(*args, **kwargs)
            except PermissionError:
                pass
        raise Timeout

    return wrapper


class Timeout(Exception):
    pass


class UnsupportedFileType(Exception):
    pass


class UnsupportedBrowser(Exception):
    pass


class UtilityAPI:
    def __init__(
        self,
        user=None,
        password=None,
        data_path=None,
        file_ext=".csv",
        headless=True,
        browser="Firefox",
        timeout=30,
        save_statements=True,
        google_sa_credentials=None,
    ):
        self._user = user
        self._password = password
        self._driver = None
        self._browser = browser
        self._headless = headless
        self._temp_download_dir = tempfile.mkdtemp()
        self._data_path = data_path or os.path.abspath(os.path.join(".", "data"))
        self._file_ext = file_ext
        self._save_statements = save_statements
        self._timeout = timeout
        self._resolutions_available = ["monthly"]

        if google_sa_credentials is not None:
            self._gdh = GoogleDriveHelper(google_sa_credentials)
        else:
            self._gdh = None

        supported_filetypes = [".csv"]
        if self._file_ext not in supported_filetypes:
            raise UnsupportedFileType(
                f"`file_ext`={self._file_ext} has an invalid filetype. Acceptable extensions are "
                + ",".join([f'"{x}"' for x in supported_filetypes])
                + "."
            )

        supported_browsers = ["Chrome", "Firefox"]
        if self._browser not in supported_browsers:
            raise UnsupportedBrowser(
                f"`browser`={self._browser} is invalid. Supported browsers are "
                + ",".join([f'"{x}"' for x in supported_browsers])
                + "."
            )

        self._monthly_history = pd.DataFrame()

        # If `data_path` is a google drive folder download the monthly data file.
        if is_gdrive_path(self._data_path):
            if google_sa_credentials is None:
                raise RuntimeError(
                    "`data_path` looks like a google drive folder, but `google_sa_credentials` is None."
                )

            folder_id = self._data_path.split("/")[-1]
            try:
                utility_folder = self._gdh.get_file_in_folder(folder_id, self.name)
            except IndexError:  # Folder doesn't exist
                utility_folder = self._gdh.create_subfolder(folder_id, self.name)

            def get_history_file(resolution, index_col):
                try:
                    data_file = self._gdh.get_file_in_folder(
                        utility_folder["id"], resolution + self._file_ext
                    )
                    file = self._gdh.download_file(
                        data_file["id"],
                        os.path.join(
                            self._temp_download_dir, resolution + self._file_ext
                        ),
                    )
                    return pd.read_csv(
                        os.path.join(
                            self._temp_download_dir, resolution + self._file_ext
                        )
                    ).set_index(index_col)
                except IndexError:  # File doesn't exist
                    return pd.DataFrame()

            self._monthly_history = get_history_file("monthly", "Date")
            hourly_history = get_history_file("hourly", "Datetime")
            if len(hourly_history):
                self._hourly_history = hourly_history

        elif os.path.exists(
            os.path.join(self._data_path, self.name, "monthly" + self._file_ext)
        ):
            # Load csv with previously cached data if it exists locally.
            self._monthly_history = pd.read_csv(
                os.path.join(self._data_path, self.name, "monthly" + self._file_ext)
            ).set_index("Date")

            if os.path.exists(
                os.path.join(self._data_path, self.name, "hourly" + self._file_ext)
            ):
                self._hourly_history = pd.read_csv(
                    os.path.join(self._data_path, self.name, "hourly" + self._file_ext)
                ).set_index("Datetime")

        self._monthly_history.index = pd.to_datetime(self._monthly_history.index)
        if hasattr(self, "_hourly_history"):
            self._hourly_history.index = pd.to_datetime(self._hourly_history.index)

    def _init_driver(self):
        if self._browser == "Chrome":
            options = webdriver.ChromeOptions()
            prefs = {"download.default_directory": self._temp_download_dir}
            options.add_experimental_option("prefs", prefs)
            if self._headless:
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--headless")
                options.add_argument("--disable-gpu")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
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
                "application/pdf,text/plain,application/text,text/xml,application/xml,"
                "application/force-download",
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

    def history(self, resolution="monthly"):

        if resolution not in self._resolutions_available:
            raise RuntimeError(
                "resolution must be one of: "
                + f"{ ', '.join(self._resolutions_available) }."
            )
        if resolution == "monthly":
            return self._monthly_history
        elif resolution == "hourly":
            return self._hourly_history

    def __del__(self):
        if self._driver:
            self._close_driver()

    def _close_driver(self):
        self._driver.close()
        self._driver = None

    def download_link(self, link, ext):
        # remove all files in the temp dir
        files = os.listdir(self._temp_download_dir)
        for file in files:
            os.remove(os.path.join(self._temp_download_dir, file))

        # add a random delay to keep from being banned
        time.sleep(1 * random.random() * 3)

        # download the link
        link.click()

        t_start = time.time()
        filepath = None
        # wait for the file to finish downloading
        while time.time() - t_start < self._timeout:
            files = glob.glob(os.path.join(self._temp_download_dir, "*.%s" % ext))
            if len(files) and os.path.getsize(files[0]) > 0:
                filepath = os.path.join(self._temp_download_dir, files[0])
                time.sleep(0.5)
                break
        if not filepath:
            raise Timeout
        return filepath

    def get_statements(self):
        # If `data_path` is a google drive url, upload pdfs to gdrive.
        if is_gdrive_path(self._data_path):
            statements_folder = self._get_gdrive_statements_folder()
            return self._gdh.get_files_in_folder(statements_folder["id"], "*.pdf")
        else:
            # If `data_path` is a local path
            return glob.glob(
                os.path.join(self._data_path, self.name, "statements", "*.pdf")
            )

    def _get_gdrive_statements_folder(self):
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
            return statements_folder
        return None

    def _copy_statements_to_data_path(self, pdf_files):
        # If `data_path` is a google drive url, upload pdfs to gdrive.
        if is_gdrive_path(self._data_path):
            statements_folder = self._get_gdrive_statements_folder()
            for local_path in pdf_files:
                if (
                    self._gdh.file_exists_in_folder(
                        statements_folder["id"], os.path.split(local_path)[-1]
                    )
                    == False
                ):
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
        return pdf_files

    def update(self, max_downloads=None):
        # Download any new statements.
        start_date = None
        if len(self._monthly_history):
            start_date = (
                arrow.get(self._monthly_history.sort_index().index[-1]).date()
                + dt.timedelta(days=1)
            ).isoformat()
        pdf_files = self.download_statements(
            start_date=start_date, max_downloads=max_downloads
        )
        return self.extract_data_from_statements(pdf_files)

    def extract_data_from_statements(self, pdf_files):
        df_new_rows = pd.DataFrame()
        cached_invoice_dates = list(self._monthly_history.index)
        for pdf in pdf_files:
            # Scrape data from pdf file
            date = os.path.splitext(os.path.basename(pdf))[0].split(" - ")[0]

            # If we've already scraped this pdf, continue
            if date not in cached_invoice_dates:
                print("Scrape data from %s" % pdf)
                try:
                    result = self.extract_data(pdf)
                    df_new_rows = df_new_rows.append(
                        pd.DataFrame(result, index=[None]).set_index("Date")
                    )
                except Exception:
                    traceback.print_exc()
        self._monthly_history = self._monthly_history.append(df_new_rows)
        self._monthly_history.sort_index(inplace=True)
        self._monthly_history.index = pd.to_datetime(self._monthly_history.index)
        self._update_history()
        return df_new_rows

    def _update_history(self):
        # Update history

        # If `data_path` is a google drive folder, upload the history file(s).
        if is_gdrive_path(self._data_path):
            folder_id = self._data_path.split("/")[-1]
            try:
                utility_folder = self._gdh.get_file_in_folder(folder_id, self.name)
            except IndexError:
                utility_folder = self._gdh.create_subfolder(folder_id, self.name)

            def upload_file(resolution):
                try:
                    data_file = self._gdh.get_file_in_folder(
                        utility_folder["id"], resolution + self._file_ext
                    )
                    self._gdh.upload_file(
                        data_file["id"],
                        os.path.join(
                            self._temp_download_dir, resolution + self._file_ext
                        ),
                    )
                except IndexError:
                    data_file = self._gdh.create_file_in_folder(
                        utility_folder["id"],
                        os.path.join(
                            self._temp_download_dir, resolution + self._file_ext
                        ),
                    )

            self._monthly_history.to_csv(
                os.path.join(self._temp_download_dir, "monthly" + self._file_ext)
            )
            upload_file("monthly")

            if hasattr(self, "_hourly_history"):
                self._hourly_history.to_csv(
                    os.path.join(self._temp_download_dir, "hourly" + self._file_ext)
                )
                upload_file("hourly")
        else:
            # Create directories if necessary
            os.makedirs(os.path.join(self._data_path, self.name), exist_ok=True)

            # Update csv file
            self._monthly_history.to_csv(
                os.path.join(self._data_path, self.name, "monthly" + self._file_ext)
            )

            if hasattr(self, "_hourly_history"):
                self._hourly_history.to_csv(
                    os.path.join(self._data_path, self.name, "hourly" + self._file_ext)
                )
