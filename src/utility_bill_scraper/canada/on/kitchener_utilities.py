import calendar
import os
import re
import shutil
import tempfile
import time

import arrow
import pandas as pd
from bs4 import BeautifulSoup
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
)

from utility_bill_scraper import (
    Timeout,
    UtilityAPI,
    convert_divs_to_df,
    format_fields,
    pdf_to_html,
)


NAME = "Kitchener Utilities"


def get_summary(soup):
    def find_seq_id(tag):
        return tag.name == "div" and tag.decode().find("SEQ-ID") >= 0

    def find_account_summary(tag):
        return tag.name == "span" and tag.decode().find("Your Account Summary") >= 0

    summary_fields = format_fields(soup.find_all(find_account_summary)[0].contents)
    summary_data = format_fields(
        soup.find_all(find_seq_id)[0].next_sibling.contents[0].contents
    )

    summary_dict = dict(zip(summary_fields[1:], summary_data))

    def find_charges(name):
        def find_matching_div(tag):
            return tag.name == "div" and tag.decode().find(name) >= 0

        tag = soup.find(find_matching_div)

        # Extract the top pixel coordinate.
        match = re.search(r"top:(?P<top>\d+)px", tag.decode())
        top = match.groups()[0]

        # Find the second div with the same top pixel coordinate.
        return format_fields(
            soup.find_all(style=re.compile("top:%spx" % top))[1].span.contents
        )[0]

    summary_dict["Water Charges"] = find_charges("Water charges")
    summary_dict["Gas Charges"] = find_charges("Gas charges")

    return summary_dict


def get_water_consumption(soup):
    def find_total_consumption(tag):
        return tag.name == "div" and tag.decode().find("Total Consumption") >= 0

    div_list = soup.find_all(find_total_consumption)

    # Find the div containing 3 fields (gas has an extra
    # 'Billing Conversion Multiplier'). Note that it is possible to have
    # more than one consumption section.
    tags = [x for x in div_list if len(format_fields(x.contents[0])) == 3]
    assert len(tags) == 1
    tag = tags[0]

    # Extract the top pixel coordinate.
    match = re.search(r"top:(?P<top>\d+)px", tag.decode())
    top = match.groups()[0]

    # Match all divs with the same top pixel coordinate.
    def find_matching_top(tag):
        return tag.name == "div" and tag.decode().find("top:%spx" % top) >= 0

    divs = [format_fields(x.contents[0]) for x in soup.find_all(find_matching_top)]
    return dict(zip(divs[0], divs[2]))


def get_water_and_sewer_charges(soup):
    def find_water_consumption(tag):
        return (
            (tag.name == "div")
            and (tag.decode().find("Consumption") >= 0)
            and (tag.decode().find("Total Consumption") == -1)
        )

    water_div = soup.find_all(find_water_consumption)[0]
    water_type = format_fields(water_div.next_sibling.contents[0])

    result = {"Time period": water_type[0]}
    water_type = water_type[1:]

    consumption = format_fields(water_div.next_sibling.next_sibling.contents[0])
    rates = format_fields(
        water_div.next_sibling.next_sibling.next_sibling.next_sibling.contents[0]
    )
    charges = format_fields(
        water_div.next_sibling.next_sibling.next_sibling.next_sibling.next_sibling.contents[
            0
        ]
    )

    for x in range(len(water_type)):
        result[water_type[x]] = {
            "Consumption": consumption[x],
            "Rate": rates[x],
            "Charges": charges[x],
        }
    return result


def get_water_charges(soup):
    data = get_water_and_sewer_charges(soup)
    types = ["Water", "Sewer"]
    return dict(zip(types, [data[x]["Charges"] for x in types]))


def get_water_rates(soup):
    data = get_water_and_sewer_charges(soup)
    types = ["Water", "Sewer"]
    return dict(zip(types, [data[x]["Rate"] for x in types]))


def get_gas_consumption(soup):
    def find_total_consumption(tag):
        return tag.name == "div" and tag.decode().find("Total Consumption") >= 0

    div_list = soup.find_all(find_total_consumption)

    # Find divs containing 4 fields (gas has an extra
    # 'Billing Conversion Multiplier'). Note that it is possible to have
    # more than one consumption section.
    tags = [x for x in div_list if len(format_fields(x.contents[0])) > 3]
    assert len(tags) == 1
    tag = tags[0]

    # Extract the top pixel coordinate.
    match = re.search(r"top:(?P<top>\d+)px", tag.decode())
    top = match.groups()[0]

    # Match all divs with the same top pixel coordinate.
    def find_matching_top(tag):
        return tag.name == "div" and tag.decode().find("top:%spx" % top) >= 0

    divs = [format_fields(x.contents[0]) for x in soup.find_all(find_matching_top)]

    return dict(zip(divs[0], divs[2]))


def get_gas_charges(soup):
    try:
        # Find the bounding box that defines the gas section.
        pos_re = r"left:(?P<left>\d+)px.*top:(?P<top>\d+)px.*width:(?P<width>\d+)px.*height:(?P<height>\d+)"

        def find_gas_section(tag):
            return tag.name == "div" and tag.decode().find("GAS") >= 0

        tag = soup.find(find_gas_section)
        pos = re.search(pos_re, tag.decode()).groupdict()
        top_bound = int(pos["top"])

        def find_gas_charges(tag):
            return tag.name == "div" and tag.decode().find("Gas charges") >= 0

        tag = soup.find(find_gas_charges)
        pos = re.search(pos_re, tag.decode()).groupdict()
        bottom_bound = int(pos["top"])

        # Find all of the div tags within this bounding box.
        def find_divs_within_bounds(tag):
            match = re.search(pos_re, tag.decode())
            if match:
                top = int(match.groupdict()["top"])
                return top >= top_bound and top < bottom_bound and tag.name == "div"
            return False

        df = convert_divs_to_df(soup.find_all(find_divs_within_bounds))
        df["fields_str"] = [str(x) for x in df["fields"]]
        df = df.sort_values(["top", "left"])

        # Charges can be grouped in different sections (e.g., if the gas rate
        # changes in the middle of the month). We only care about the last
        # section, because it contains the Fixed Delivery Charge.
        charges = df[
            df["left"] > df[df["fields_str"] == "[u'Charges']"]["left"].iloc[0]
        ].iloc[-1]["fields"]
        charge_desc = df[df["fields_str"].str.find(" days") >= 0].iloc[-1]["fields"][1:]
        return dict(zip(charge_desc[-len(charges) :], charges))
    except AttributeError as error:
        print("Error scraping gas charges")
    return {}


def get_gas_rates(soup):
    def find_gas_rates(tag):
        return tag.name == "div" and tag.decode().find("Gas Fixed Delivery Charge") >= 0

    gas_div = soup.find_all(find_gas_rates)[0]
    gas_fields = format_fields(gas_div.contents[0])
    gas_fields = gas_fields[1:]
    gas_rates = format_fields(
        gas_div.next_sibling.next_sibling.next_sibling.contents[0]
    )
    format_fields(
        gas_div.next_sibling.next_sibling.next_sibling.next_sibling.contents[0]
    )

    return dict(
        zip(
            [
                x + " Rate"
                for x in gas_fields
                if (x.find("HST") == -1) and x.find("Fixed") == -1
            ],
            gas_rates,
        )
    )


class KitchenerUtilitiesAPI(UtilityAPI):
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

    def _login(self):
        self._driver.get(
            "https://ebilling.kitchener.ca/sap/bc/ui5_ui5/sap/ZUMCUI5/index.html"
        )
        self._driver.find_element_by_id("CANCEL_BUTTON ").click()
        self._driver.find_element_by_id("__field1").send_keys(self._user)
        self._driver.find_element_by_id("__field0").send_keys(self._password)
        self._driver.find_element_by_id("__button0").click()

    def _get_header_nav_bar(self):
        result = None
        t_start = time.time()
        while time.time() - t_start < self._timeout:
            try:
                pages = self._driver.find_element_by_id(
                    "headerNavigationBar"
                ).find_elements_by_tag_name("li")
                keys = [x.text for x in pages]
                result = dict(zip(keys, pages))
                result.pop("", None)
                return result
            except NoSuchElementException:
                pass
        raise Timeout

    def _get_contracts(self):
        # Pick the account (e.g., "Gas", "Water and Sewer", "Stormwater")
        contract_table = self._driver.find_element_by_id(
            "ContractTable-table"
        ).find_element_by_tag_name("tbody")
        rows = contract_table.find_elements_by_tag_name("tr")

        contracts = [x.find_elements_by_tag_name("td")[0] for x in rows]
        keys = [x.text for x in contracts]
        return dict(zip(keys, contracts))

    def _first_page(self):
        # Get a list of the pages available
        t_start = time.time()
        link = None
        while time.time() - t_start < self._timeout:
            try:
                link = self._driver.find_element_by_id(
                    "__table1-paginator--firstPageLink"
                )
                link.location_once_scrolled_into_view
                link.click()
                return
            except NoSuchElementException:
                pass
            except StaleElementReferenceException:
                pass
        raise Timeout

    def _get_pages(self):
        # Get a list of the pages available
        table = None
        t_start = time.time()
        while time.time() - t_start < self._timeout:
            try:
                table = self._driver.find_element_by_id("__table1-paginator-pages")
                time.sleep(1)
                break
            except NoSuchElementException:
                pass

        if table:
            time.sleep(0.5)
            pages = table.find_elements_by_tag_name("li")
            keys = [int(x.text) for x in pages]
            return dict(zip(keys, pages))
        else:
            raise Timeout
        return None

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

            def get_data():
                # Iterate through the statements in reverse chronological order
                # (i.e., newest statements are first).

                billing_table = self._driver.find_element_by_id("__table1-table")

                rows = [
                    [y for y in x.find_elements_by_tag_name("td")]
                    for x in billing_table.find_element_by_tag_name(
                        "tbody"
                    ).find_elements_by_tag_name("tr")
                ]

                data = []
                date = None
                for row in rows:
                    row_data = [x.text for x in row[1:]]
                    if row_data[0] == "":
                        continue

                    date = arrow.get(row_data[1], "MM/DD/YYYY").date()

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
                        % (date.isoformat(), self.name, row_data[3]),
                    )

                    downloaded_files.append(new_filepath)
                    if not os.path.exists(new_filepath):
                        # download the pdf statement
                        for img in row[0].find_elements_by_tag_name("img"):
                            if img.get_property("title") == "PDF":
                                filepath = self.download_link(img, "pdf")
                                shutil.move(filepath, new_filepath)

                return data, date

            self._get_header_nav_bar()["BILLING"].click()
            self._first_page()

            pages_downloaded = []
            pages_to_download = list(self._get_pages().keys())
            data = []
            while len(pages_to_download):
                pages = self._get_pages()

                # Add any new pages that are not in our list
                for x in pages.keys():
                    if x not in pages_to_download and x not in pages_downloaded:
                        pages_to_download += [x]

                # Download the first page in the list
                i = pages_to_download.pop(0)

                pages[i].click()
                pages_downloaded += [i]
                time.sleep(1)
                page_data, last_date = get_data()
                data += page_data

                # Because the statments are in reverse chronological order, we
                # can stop as soon as we've checked a date that is prior to the
                # start date.
                if start_date and last_date < start_date:
                    break
        finally:
            self._close_driver()

        if self._save_statements:
            downloaded_files = self._copy_statements_to_data_path(downloaded_files)

        return downloaded_files

    def get_consumption_history(self, contract):
        self._init_driver()

        try:

            def get_data():
                # The Consumption history div (this contains all of the data we are interested in)
                consumption_history = (
                    self._driver.find_element_by_id("contractConsumptionHistory")
                    .find_element_by_id("__table1-table")
                    .find_element_by_tag_name("tbody")
                )
                rows = consumption_history.find_elements_by_tag_name("tr")
                data = [
                    [y.text for y in x.find_elements_by_tag_name("td")] for x in rows
                ]
                return data

            self._login()

            self._get_header_nav_bar()["ACCOUNTS"].click()
            self._get_contracts()[contract].click()

            # Click on the "Consumption History" tab
            link = self._driver.find_element_by_id("contractDetailNavigationBarItem2")
            link.location_once_scrolled_into_view
            link.click()
            time.sleep(0.5)

            data = []
            for page in self._get_pages().keys():
                link = self._get_pages()[page]
                link.location_once_scrolled_into_view
                link.click()
                data += get_data()

            # sum values that have the same date
            dates = [x for x, y in data]
            results = dict(zip(dates, [0] * len(dates)))
            results.pop("", None)
            for date, consumption in data:
                if date != "":
                    results[date] += float(consumption)
        finally:
            self._close_driver()

        def convert_to_series(data):
            dates = [
                arrow.get("%s 01 %s" % tuple(x.split(" ")), "MMMM DD YYYY").date()
                for x in list(data.keys())
            ]
            dates = [
                "%d-%02d-%02d"
                % (x.year, x.month, calendar.monthrange(x.year, x.month)[1])
                for x in dates
            ]
            return pd.Series(list(data.values()), index=dates)

        return convert_to_series(results)

    def extract_data(self, pdf_file):
        """Extract data from a pdf_file.

        Parameters
        ----------
        pdf_file :
            Path to a pdf file.

        Returns
        ----------
        dict of key/value pairs extracted from the pdf.
        Must include:
            Date: str
            Total: str
        """
        html_file = pdf_to_html(pdf_file)
        with open(html_file, "r", encoding="utf8") as f:
            soup = BeautifulSoup(f, "html.parser")
        os.remove(html_file)

        result = get_summary(soup)
        # To do: several functions were broken when updating to python3
        result["Water Consumption"] = get_water_consumption(soup)["Total Consumption"]
        result["Gas Consumption"] = get_gas_consumption(soup)["Total Consumption"]

        if "Pre-authorized Withdrawal" in result.keys():
            result["Total"] = result.pop("Pre-authorized Withdrawal")
        elif "Total Due" in result["summary"].keys():
            result["Total"] = result.pop("Total Due")
        else:
            raise Exception("Couldn't find amount due!")
        result["Date"] = str(arrow.get(result.pop("Issue Date"), "MMM DD YYYY").date())

        return result
