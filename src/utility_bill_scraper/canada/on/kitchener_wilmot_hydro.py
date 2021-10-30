import glob
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

from utility_bill_scraper import (
    Timeout,
    UtilityAPI,
    format_fields,
    pdf_to_html,
    wait_for_element,
)


def get_name():
    return "Kitchener-Wilmot Hydro"


def get_electricity_consumption(soup):
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


def get_billing_date(soup):
    def find_billing(tag):
        return tag.name == u"div" and tag.decode().find("BILLING DATE") >= 0

    match = re.search(
        "([A-Z]+)\s+(\d+)\s+(\d+)",
        format_fields(
            soup.find_all(find_billing)[0].next_sibling.next_sibling.span.contents
        )[0],
    )
    month, day, year = match.groups()

    return arrow.get("%s %s %s" % (month, day, year), "MMM DD YYYY").date().isoformat()


def get_electricity_rates(soup):
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


def get_amount_due(soup):
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

    amount_due = format_fields(
        tags[np.nonzero(distance == np.min(distance))[0][0]].span
    )[0]

    index = str(amount_due).find("CR")
    if index >= 0:
        amount_due = (-1) * float(amount_due[:index])

    return amount_due


class KitchenerWilmotHydroAPI(UtilityAPI):
    name = get_name()

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
        super().__init__(
            user=user,
            password=password,
            data_path=data_path,
            file_ext=file_ext,
            headless=headless,
            timeout=timeout,
            save_statements=save_statements,
            google_sa_credentials=google_sa_credentials,
        )

    def _login(self):
        self._driver.get("https://www3.kwhydro.on.ca/app/login.jsp")
        self._driver.find_element_by_id("accessCode").send_keys(self._user)
        self._driver.find_element_by_id("password").send_keys(self._password)
        self._driver.find_element_by_xpath(
            '//*[@id="login-form"]/div[3]/button'
        ).click()

    def _download_link(self, link, ext, timeout=5):
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
        while time.time() - t_start < timeout:
            files = glob.glob(os.path.join(self._temp_download_dir, "*.%s" % ext))
            if len(files):
                filepath = os.path.join(self._temp_download_dir, files[0])
                time.sleep(0.5)
                break
        if not filepath:
            raise Timeout
        return filepath

    def download_hourly_data(self, start_date=None, end_date=None):
        self._init_driver(headless=False)

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
                date_range = pd.date_range(start_date, yesterday, freq="M").append(
                    pd.DatetimeIndex([yesterday])
                )
            else:
                date_range = pd.date_range(start_date, end_date, freq="M")
            date_range = [x.date() for x in date_range]

            self._hourly_data_directory = os.path.join(
                self._data_directory, self.name, "hourly data"
            )

            for date in date_range:
                if not os.path.isdir(self._hourly_data_directory):
                    os.makedirs(self._hourly_data_directory)

                new_filepath = os.path.join(
                    self._hourly_data_directory, "%s.csv" % (date.isoformat())
                )

                if os.path.exists(new_filepath):
                    continue

                print(
                    "Downloading hourly data for %d-%02d-01 to %d-%02d-%02d..."
                    % (date.year, date.month, date.year, date.month, date.day)
                )

                # Wait a random period between requests so that we don't get blocked
                time.sleep(5 + random.random() * 5)

                url = (
                    "https://www3.kwhydro.on.ca/app/capricorn?para=smartMeterConsum&inquiryType=hydro"
                    "&fromYear=%d&fromMonth=%02d&fromDay=%02d&toYear=%d&toMonth=%02d&toDay=%02d"
                    % (date.year, date.month, 1, date.year, date.month, date.day)
                )
                self._driver.get(url)

                def is_valid_date_range():
                    valid_date_range = True
                    try:
                        valid_date_range = not self._driver.find_element_by_class_name(
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

                filepath = self._download_link(
                    self._driver.find_element_by_id("download"), "csv"
                )

                # Read the csv file
                df_csv = pd.read_csv(filepath)[
                    :-1
                ]  # Ignore last line which is just a note

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

                # Reformat the data indexed by a timestamp
                for i, row in df_csv.iterrows():
                    df.loc[row[0], "kWh"] = df_csv.loc[i][1:25].values

                # Offset index by 1hr
                df.index = [x + datetime.timedelta(hours=1) for x in df.index]

                # If we're downloading data from the current month, delete
                # previous files
                if date == yesterday:
                    files = glob.glob(
                        os.path.join(
                            self._hourly_data_directory,
                            "%d-%02d-*.csv" % (date.year, date.month),
                        )
                    )
                    for f in files:
                        os.remove(f)

                # Save the reformatted data
                df.to_csv(new_filepath)
        finally:
            self._close_driver()

    def extract_data(self, pdf):
        html_file = pdf_to_html(pdf)
        with open(html_file, "r", encoding="utf8") as f:
            soup = BeautifulSoup(f, "html.parser")
        os.remove(html_file)

        date = get_billing_date(soup)
        amount_due = get_amount_due(soup)
        "%s - %s - $%.2f.pdf" % (date, get_name(), amount_due)

        rates = get_electricity_rates(soup)
        consuption = get_electricity_consumption(soup)

        result = {
            "Date": date,
            "Amount Due": amount_due,
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
        return result

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
            link = self._driver.find_element_by_link_text("Bills & Payment")
            link.location_once_scrolled_into_view
            link.click()

            self._driver.switch_to.frame("iframe-BILLINQ")
            time.sleep(0.5)

            @wait_for_element
            def get_bills_table():
                return self._driver.find_element_by_id("billsTable")

            @wait_for_element
            def get_bills_table_rows(bills_table):
                rows = [
                    [y for y in x.find_elements_by_tag_name("td")]
                    for x in bills_table.find_element_by_tag_name(
                        "tbody"
                    ).find_elements_by_tag_name("tr")[2:]
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
                    img = row[0].find_element_by_tag_name("img")
                    filepath = self.download_link(img, "pdf")
                    shutil.move(filepath, new_filepath)
        finally:
            self._close_driver()

        return downloaded_files
