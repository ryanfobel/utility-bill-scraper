import glob
import datetime
import os
import random
import re
import shutil
import tempfile
import time

import arrow
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from utility_bill_scraper import (
    Timeout,
    UtilityAPI,
    format_fields,
    pdf_to_html,
    wait_for_element,
    is_number,
)


re_consumption = (
    "((?P<start_date>[a-zA-Z]+\s+\d+"
    ",\s+[\d]{4})\s+to\s+(?P<end_date>[a-zA-Z]+"
    "\s+\d+,\s+[\d]{4}).+)*Off-Peak:\s+"
    "(?P<off_peak_use>[\d]+\.[\d]+)\s+kWh\s+@\s+"
    "\$(?P<off_peak_rate>[\d]+\.[\d]+).+Mid-Peak:\s+"
    "(?P<mid_peak_use>[\d]+\.[\d]+)\s+kWh\s+@\s+"
    "\$(?P<mid_peak_rate>[\d]+\.[\d]+).+On-Peak:\s+"
    "(?P<on_peak_use>[\d]+\.[\d]+)\s+kWh\s+@\s+"
    "\$(?P<on_peak_rate>[\d]+\.[\d]+).+"
)


NAME = "Kitchener-Wilmot Hydro"


def get_consumption(soup):
    def _get_consumption(soup):
        def find_new_charges(tag):
            return tag.name == u"span" and re.search(
                re_consumption, tag.getText(), re.DOTALL
            )

        tags = soup.find_all(find_new_charges)
        df = pd.DataFrame()
        for tag in tags:
            match = re.search(re_consumption, tag.getText(), re.DOTALL)
            row_data = match.groupdict()
            row_data = {
                k: arrow.get(v, "MMMM DD, YYYY").date().isoformat()
                if v and k.endswith("date")
                else v
                for k, v in row_data.items()
            }
            row_data = {
                k: float(v) if v and is_number(v) else v for k, v in row_data.items()
            }
            df = df.append(row_data, ignore_index=True)

        return {
            k.replace("_use", "").replace("_", " "): v
            for k, v in df.sum()[["off_peak_use", "mid_peak_use", "on_peak_use"]]
            .to_dict()
            .items()
        }

    def _get_consumption_pre_2021_10(soup):
        def find_kWh(tag):
            return tag.name == u"span" and (
                tag.decode().find("kWh Off Peak") >= 0
                or tag.decode().find("kWh Mid Peak") >= 0
                or tag.decode().find("kWh On Peak") >= 0
            )

        fields = []
        for x in soup.find_all(find_kWh):
            fields += format_fields(x)

        data = {"off peak": 0, "mid peak": 0, "on peak": 0}

        for x in fields:
            if x.find("kWh Off Peak") > 0:
                data["off peak"] += float(x[: x.find("kWh Off Peak")])
            elif x.find("kWh Mid Peak") > 0:
                data["mid peak"] += float(x[: x.find("kWh Mid Peak")])
            elif x.find("kWh On Peak") > 0:
                data["on peak"] += float(x[: x.find("kWh On Peak")])

        return data

    try:
        return _get_consumption(soup)
    except:
        return _get_consumption_pre_2021_10(soup)


def get_rates(soup):
    def _get_rates(soup):
        def find_new_charges(tag):
            return tag.name == u"span" and re.search(
                re_consumption, tag.getText(), re.DOTALL
            )

        tags = soup.find_all(find_new_charges)
        df = pd.DataFrame()
        for tag in tags:
            match = re.search(re_consumption, tag.getText(), re.DOTALL)
            row_data = match.groupdict()
            row_data = {
                k: arrow.get(v, "MMMM DD, YYYY").date().isoformat()
                if v and k.endswith("date")
                else v
                for k, v in row_data.items()
            }
            row_data = {
                k: float(v) if v and is_number(v) else v for k, v in row_data.items()
            }
            df = df.append(row_data, ignore_index=True)

        return {
            k.replace("_rate", "").replace("_", " "): v
            for k, v in df.iloc[0][["off_peak_rate", "mid_peak_rate", "on_peak_rate"]]
            .to_dict()
            .items()
        }

    def _get_rates_pre_2021_10(soup):
        def find_kWhOffPeak(tag):
            return tag.name == u"div" and tag.decode().find("kWh Off Peak") >= 0

        tag = soup.find(find_kWhOffPeak)
        match = re.search("top:(?P<top>\d+)px", tag.decode())
        top = match.groups()[0]

        # match all divs with the same top pixel coordinate
        def find_matching_top(tag):
            return tag.name == u"div" and tag.decode().find("top:%spx" % top) >= 0

        for x in soup.find_all(find_matching_top):
            fields = format_fields(x.span)
            if len(fields) > 0 and str(fields[0]).find("at $") == 0:
                rates = [float(x[4:]) for x in fields]
                break

        return dict(zip(["off peak", "on peak", "mid peak"], rates))

    try:
        return _get_rates(soup)
    except:
        return _get_rates_pre_2021_10(soup)


def get_billing_date(soup):
    def _get_date(soup):
        try:

            def find_billing(tag):
                return tag.name == u"span" and tag.decode().find("Invoice Date") >= 0

            match = re.search(
                "([A-Z]+)\s+(\d+),\s+(\d+)",
                format_fields(soup.find_all(find_billing)[0].next_sibling.contents)[0],
            )
            return match.groups()
        except:
            return _get_date_pre_2021_10(soup)

    def _get_date_pre_2021_10(soup):
        # Valid for invoices before 2021-10
        def find_billing(tag):
            return tag.name == u"div" and tag.decode().find("BILLING DATE") >= 0

        match = re.search(
            "([A-Z]+)\s+(\d+)\s+(\d+)",
            format_fields(
                soup.find_all(find_billing)[0].next_sibling.next_sibling.span.contents
            )[0],
        )
        return match.groups()

    month, day, year = _get_date(soup)
    return arrow.get("%s %s %s" % (month, day, year), "MMM DD YYYY").date().isoformat()


def get_amount_due(soup):
    def _get_amount_due(soup):
        def find_billing(tag):
            return (
                tag.name == u"div"
                and tag.decode().find("Amount Due") >= 0
                and tag.decode().find("Total Amount Due") == -1
                and re.search("[\d]+\.[\d]+", tag.next_sibling.decode())
            )

        match = re.search(
            "([\d]+\.[\d]+)", soup.find_all(find_billing)[0].next_sibling.decode()
        )
        return float(match.groups()[0])

    def _get_amount_due_pre_2021_10(soup):
        def find_new_charges(tag):
            return tag.name == u"div" and tag.decode().find("New Charges") >= 0

        tag = soup.find(find_new_charges)
        match = re.search("top:(?P<top>\d+)px", tag.decode())
        top = float(match.groups()[0])

        def find_left_pos(tag):
            if tag.name == u"div":
                match = re.search("left:(?P<left>\d+)px", tag.decode())
                if match:
                    left = float(match.groups()[0])
                    return left >= 120 and left <= 132
            return False

        tags = soup.find_all(find_left_pos)

        distance = []
        for tag in tags:
            match = re.search("top:(?P<top>\d+)px", tag.decode())
            distance.append(abs(float(match.groups()[0]) - top))

        return format_fields(tags[np.nonzero(distance == np.min(distance))[0][0]].span)[
            0
        ]

    try:
        amount_due = _get_amount_due(soup)
    except:
        amount_due = _get_amount_due_pre_2021_10(soup)

    index = str(amount_due).find("CR")
    if index >= 0:
        amount_due = (-1) * float(amount_due[:index])
    return amount_due


class EnovaPowerAPI(UtilityAPI):
    name = NAME

    def __init__(
        self,
        user=None,
        password=None,
        data_path=None,
        file_ext=".csv",
        headless=True,
        browser="Firefox",
        timeout=10,
        save_statements=True,
        google_sa_credentials=None,
    ):
        super().__init__(
            user=user,
            password=password,
            data_path=data_path,
            file_ext=file_ext,
            headless=headless,
            browser=browser,
            timeout=timeout,
            save_statements=save_statements,
            google_sa_credentials=google_sa_credentials,
        )
        self._resolutions_available.append("hourly")
        if not hasattr(self, "_hourly_history"):
            self._hourly_history = pd.DataFrame()

    def _login(self):
        self._driver.get("https://myaccount.enovapower.com/app/login.jsp")
        self._driver.find_element(By.ID, "accessCode").send_keys(self._user)
        self._driver.find_element(By.ID, "password").send_keys(self._password)
        self._driver.find_element(By.ID, "login_btn").click()

    def download_hourly_data(self, start_date=None, end_date=None):
        self._init_driver()

        df_new_rows = pd.DataFrame()

        try:
            self._login()

            yesterday = arrow.get().date() - datetime.timedelta(days=1)

            if not start_date:
                start_date = "%d-%02d-01" % (yesterday.year - 2, yesterday.month)
            start_date = arrow.get(start_date).date()

            if end_date:
                end_date = arrow.get(end_date).date()
            else:
                end_date = arrow.get().date()

            if end_date > start_date and end_date > yesterday:
                date_range = pd.date_range(start_date, yesterday, freq="ME").union(
                    pd.DatetimeIndex([yesterday])
                )
            else:
                date_range = pd.date_range(start_date, end_date, freq="ME")
            date_range = [x.date() for x in date_range]

            last_update = None
            if len(self._hourly_history):
                last_update = self._hourly_history.index[-1].date()

            for date in date_range:
                if last_update and date <= last_update:
                    continue

                print(
                    "Downloading hourly data for %d-%02d-01 to %d-%02d-%02d..."
                    % (date.year, date.month, date.year, date.month, date.day)
                )

                # Wait a random period between requests so that we don't get blocked
                time.sleep(5 + random.random() * 5)

                # Navigate directly to the Electric Downloads page (Green Button Downloads)
                # This is a sub-tab within the Smart Meter section
                url = "https://myaccount.enovapower.com/app/capricorn?para=greenButtonPromptV3&inquiryType=electric&tab=GBDMD&deviceLandingPage=GBDMD"
                self._driver.get(url)

                # Wait for the date input fields to be present
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC

                wait = WebDriverWait(self._driver, self._timeout)
                wait.until(EC.presence_of_element_located((By.ID, "GB_fromDate")))

                # Set the date range in the Electric Downloads section (Green Button section)
                # Format dates as MM/DD/YYYY
                from_date_str = "%02d/01/%d" % (date.month, date.year)
                to_date_str = "%02d/%02d/%d" % (date.month, date.day, date.year)

                # Set the visible date fields
                from_date_field = self._driver.find_element(By.ID, "GB_fromDate")
                from_date_field.clear()
                from_date_field.send_keys(from_date_str)

                to_date_field = self._driver.find_element(By.ID, "GB_toDate")
                to_date_field.clear()
                to_date_field.send_keys(to_date_str)

                # Set to Hourly granularity
                # The radio button is hidden inside a Bootstrap button group, so click the label instead
                hourly_labels = self._driver.find_elements(By.XPATH, '//label[contains(@class, "btn") and .//input[@name="hourlyOrDaily"][@value="Hourly"]]')
                if hourly_labels:
                    self._driver.execute_script("arguments[0].scrollIntoView(true);", hourly_labels[0])
                    time.sleep(0.5)
                    hourly_labels[0].click()

                time.sleep(1)  # Brief wait after setting options

                def is_valid_date_range():
                    valid_date_range = True
                    try:
                        valid_date_range = not self._driver.find_element(By.CLASS_NAME,
                            "alert.alert-danger"
                        ).text.startswith(
                            "You are not authorized to view the selected date range."
                        )
                    except NoSuchElementException:
                        pass
                    return valid_date_range

                # Check if this date range is valid
                if not is_valid_date_range():
                    print("  No data for this date range.")
                    continue

                # Wait a random period between requests so that we don't get blocked
                time.sleep(5 + random.random() * 5)

                # Wait a bit longer to ensure data is fully loaded before downloading
                time.sleep(3)

                # Click the SPREADSHEET download button (not the chart download button)
                # This is in the "Electric Downloads" section of the Smart Meter page
                download_button = self._driver.find_element(By.ID, "DownloadToSpreadsheetButton")
                download_button.click()

                # Wait for the CSV file to be downloaded
                # Enova downloads files named like "SmartMeter8493100000_YYYY-MM-DDHH.MM.SS.csv"
                import glob
                t_start = time.time()
                filepath = None
                last_size = 0
                stable_count = 0

                while time.time() - t_start < self._timeout:
                    # Look for CSV files (excluding Chrome temp files)
                    files = [f for f in glob.glob(os.path.join(self._temp_download_dir, "*.csv"))
                             if not f.endswith('.crdownload') and not f.endswith('.tmp')]

                    if files:
                        # Sort by modification time (most recent first)
                        files.sort(key=os.path.getmtime, reverse=True)
                        candidate = files[0]

                        # Check if file size is stable (hasn't changed)
                        try:
                            current_size = os.path.getsize(candidate)
                            if current_size > 0:
                                if current_size == last_size:
                                    stable_count += 1
                                    if stable_count >= 3:  # File size stable for 3 checks
                                        filepath = candidate
                                        break
                                else:
                                    stable_count = 0
                                    last_size = current_size
                        except OSError:
                            pass  # File might be in use

                    time.sleep(0.5)

                if not filepath:
                    raise Timeout("Timed out waiting for CSV download")

                # Read the csv file
                # Note: The CSV from Electric Downloads has trailing commas on data rows
                # which creates an extra empty column. We need to handle this carefully.

                # Read all lines and fix the trailing comma issue
                with open(filepath, 'r') as f:
                    lines = f.readlines()

                # Remove trailing commas from data rows (but keep header as-is)
                cleaned_lines = [lines[0]]  # Keep header
                for line in lines[1:-1]:  # Process data rows (skip last note line)
                    if line.strip().endswith(','):
                        cleaned_lines.append(line.rstrip(',\n') + '\n')
                    else:
                        cleaned_lines.append(line)

                # Parse the cleaned CSV
                import io
                df_csv = pd.read_csv(io.StringIO(''.join(cleaned_lines)))

                # Create an hourly index
                index = pd.date_range(
                    df_csv["Reading Date"].iloc[0],
                    (
                        arrow.get(df_csv["Reading Date"].iloc[-1])
                        + datetime.timedelta(days=1)
                    )
                    .date()
                    .isoformat(),
                    freq="h",
                )[:-1]

                # Create a new dataframe to store the reformatted data
                df = pd.DataFrame({"kWh": np.zeros(len(index))}, index=index)
                df.index = pd.to_datetime(df.index)
                df.index.name = "Datetime"

                # Reformat the data indexed by a timestamp
                for i, row in df_csv.iterrows():
                    date = pd.Timestamp(row["Reading Date"])
                    hourly_values = row.iloc[1:25].values
                    for hour in range(24):
                        timestamp = date + pd.Timedelta(hours=hour+1)
                        df.loc[timestamp, "kWh"] = hourly_values[hour]

                # Append the reformatted data
                if last_update:
                    df_new_rows = pd.concat([df_new_rows, df[df.index.date > last_update]])
                else:
                    df_new_rows = pd.concat([df_new_rows, df])
        finally:
            self._close_driver()

        if len(df_new_rows):
            self._hourly_history = pd.concat([self._hourly_history, df_new_rows])
            self._hourly_history.index = pd.to_datetime(self._hourly_history.index)
            self._update_history()
        return df_new_rows

    def extract_data(self, pdf):
        html_file = pdf_to_html(pdf)
        with open(html_file, "r", encoding="utf8") as f:
            soup = BeautifulSoup(f, "html.parser")
        os.remove(html_file)

        date = get_billing_date(soup)
        amount_due = get_amount_due(soup)
        "%s - %s - $%.2f.pdf" % (date, self.name, amount_due)

        rates = get_rates(soup)
        consuption = get_consumption(soup)

        return {
            "Date": date,
            "Total": amount_due,
            "Off Peak Consumption": consuption["off peak"],
            "Mid Peak Consumption": consuption["mid peak"],
            "On Peak Consumption": consuption["on peak"],
            "Total Consumption": consuption["off peak"]
            + consuption["mid peak"]
            + consuption["on peak"],
            "Off Peak Rate": rates["off peak"],
            "Mid Peak Rate": rates["mid peak"],
            "On Peak Rate": rates["on peak"],
        }

    def download_statements(self, start_date=None, end_date=None, max_downloads=None):
        download_path = tempfile.mkdtemp()
        self._init_driver()
        downloaded_files = []

        try:
            self._login()

            # convert start and end dates to date objects
            if start_date:
                start_date = arrow.get(start_date).date()
            if end_date:
                end_date = arrow.get(end_date).date()

            # Iterate through the invoices in reverse chronological order
            # (i.e., newest invoices are first).

            # Open Bills & Payment
            link = self._driver.find_element(By.LINK_TEXT, "Bills & Payment")
            link.location_once_scrolled_into_view
            link.click()
            self._driver.switch_to.frame("iframe-BILLINQ")

            @wait_for_element
            def get_bills_table():
                return self._driver.find_element(By.ID, "billsTable")

            @wait_for_element
            def get_bills_table_rows(bills_table):
                rows = [
                    [y for y in x.find_elements(By.TAG_NAME, "td")]
                    for x in bills_table.find_element(By.TAG_NAME,
                        "tbody"
                    ).find_elements(By.TAG_NAME, "tr")
                ]
                return rows

            bills_table = get_bills_table()
            rows = get_bills_table_rows(bills_table)

            data = []
            for row in rows:
                row_data = [x.text for x in row[1:]]

                date = arrow.get(row_data[0], "MMM D, YYYY").date()

                if start_date and date < start_date:
                    break

                if end_date and date > end_date:
                    continue

                if max_downloads and len(downloaded_files) >= max_downloads:
                    break

                data.append(row_data)
                new_filepath = os.path.join(
                    download_path,
                    "%s - %s - $%s.pdf"
                    % (date.isoformat(), self.name, row_data[1].split(" ")[1]),
                )

                downloaded_files.append(new_filepath)
                if not os.path.exists(new_filepath):
                    # download the pdf invoice
                    img = row[0].find_element(By.TAG_NAME, "img")
                    filepath = self.download_link(img, "pdf")
                    shutil.move(filepath, new_filepath)
        finally:
            self._close_driver()

        if self._save_statements:
            downloaded_files = self._copy_statements_to_data_path(downloaded_files)

        return downloaded_files
