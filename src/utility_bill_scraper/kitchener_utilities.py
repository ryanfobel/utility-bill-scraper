import re
import random
import time
import os
import tempfile
import glob
import calendar

import arrow
import pandas as pd
import numpy as np
from selenium import webdriver
from selenium.common.exceptions import (NoSuchElementException,
                                        ElementClickInterceptedException,
                                        StaleElementReferenceException)

from utility_bill_scraper import format_fields, is_number, convert_divs_to_df


def get_name():
    return 'Kitchener Utilities'


def get_summary(soup):
    def find_seq_id(tag):
        return tag.name == u'div' and tag.decode().find('SEQ-ID') >= 0

    def find_account_summary(tag):
        return tag.name == u'span' and tag.decode(). \
            find('Your Account Summary') >= 0

    summary_fields = format_fields(soup.find_all(
        find_account_summary)[0].contents)
    summary_data = format_fields(soup.find_all(
        find_seq_id)[0].next_sibling.contents[0].contents)

    summary_dict = dict(zip(summary_fields[1:], summary_data))

    def find_charges(name):
        def find_matching_div(tag):
            return tag.name == u'div' and tag.decode().find(
                name) >= 0

        tag = soup.find(find_matching_div)

        # Extract the top pixel coordinate.
        match = re.search('top:(?P<top>\d+)px', tag.decode())
        top = match.groups()[0]

        # Find the second div with the same top pixel coordinate.
        return format_fields(soup.find_all(
            style=re.compile('top:%spx' % top))[1].span.contents)[0]

    summary_dict[u'Water Charges'] = find_charges('Water charges')
    summary_dict[u'Gas Charges'] = find_charges('Gas charges')

    return summary_dict


def get_water_consumption(soup):
    def find_total_consumption(tag):
        return tag.name == u'div' and tag.decode().find(
            'Total Consumption') >= 0

    div_list = soup.find_all(find_total_consumption)

    # Find the div containing 3 fields (gas has an extra
    # 'Billing Conversion Multiplier'). Note that it is possible to have
    # more than one consumption section.

    tags = [x for x in div_list if len(format_fields(x.contents[0])) == 3]

    consumption = []

    for tag in tags:
        # Extract the top pixel coordinate.
        match = re.search('top:(?P<top>\d+)px', tag.decode())
        top = match.groups()[0]

        # Match all divs with the same top pixel coordinate.
        def find_matching_top(tag):
            return tag.name == u'div' and tag.decode().find('top:%spx' % top) >= 0

        divs = [format_fields(x.contents[0]) for x in soup.find_all(
            find_matching_top)]
        consumption.append(dict(zip(divs[0], divs[2])))
    return consumption


def get_water_and_sewer_charges(soup):
    def find_water_consumption(tag):
        return (tag.name == u'div') and \
            (tag.decode().find('Consumption') >= 0) and \
            (tag.decode().find('Total Consumption') == -1)

    water_div = soup.find_all(find_water_consumption)[0]
    water_type = format_fields(water_div.next_sibling.contents[0])

    result = {u'Time period': water_type[0]}
    water_type = water_type[1:]

    consumption = format_fields(
        water_div.next_sibling.next_sibling.contents[0])
    rates = format_fields(
        water_div.next_sibling.next_sibling.next_sibling.next_sibling.
        contents[0])
    charges = format_fields(
        water_div.next_sibling.next_sibling.next_sibling.next_sibling.
        next_sibling.contents[0])

    for x in range(len(water_type)):
        result[water_type[x]] = {u'Consumption': consumption[x],
                                 u'Rate': rates[x],
                                 u'Charges': charges[x]}
    return result


def get_water_charges(soup):
    data = get_water_and_sewer_charges(soup)
    types = ['Water', 'Sewer']
    return dict(zip(types, [data[x]['Charges'] for x in types]))


def get_water_rates(soup):
    data = get_water_and_sewer_charges(soup)
    types = ['Water', 'Sewer']
    return dict(zip(types, [data[x]['Rate'] for x in types]))


def get_gas_consumption(soup):
    def find_total_consumption(tag):
        return tag.name == u'div' and tag.decode().find(
            'Total Consumption') >= 0

    div_list = soup.find_all(find_total_consumption)

    # Find divs containing 4 fields (gas has an extra
    # 'Billing Conversion Multiplier'). Note that it is possible to have
    # more than one consumption section.
    tags = [x for x in div_list if len(format_fields(x.contents[0])) > 3]

    consumption = []
    for tag in tags:
        # Extract the top pixel coordinate.
        match = re.search('top:(?P<top>\d+)px', tag.decode())
        top = match.groups()[0]

        # Match all divs with the same top pixel coordinate.
        def find_matching_top(tag):
            return tag.name == u'div' and tag.decode().find('top:%spx' % top) >= 0

        divs = [format_fields(x.contents[0]) for x in soup.find_all(
                find_matching_top)]

        consumption.append(dict(zip(divs[0], divs[2])))
    return consumption


def get_gas_charges(soup):
    try:
        # Find the bounding box that defines the gas section.
        pos_re = ('left:(?P<left>\d+)px.*top:(?P<top>\d+)px.*'
                'width:(?P<width>\d+)px.*height:(?P<height>\d+)')

        def find_gas_section(tag):
            return tag.name == u'div' and tag.decode().find(
                'GAS') >= 0

        tag = soup.find(find_gas_section)
        pos = re.search(pos_re, tag.decode()).groupdict()
        top_bound = int(pos['top'])

        def find_gas_charges(tag):
            return tag.name == u'div' and tag.decode().find(
                'Gas charges') >= 0

        tag = soup.find(find_gas_charges)
        pos = re.search(pos_re, tag.decode()).groupdict()
        bottom_bound = int(pos['top'])

        # Find all of the div tags within this bounding box.
        def find_divs_within_bounds(tag):
            match = re.search(pos_re, tag.decode())
            if match:
                top = int(match.groupdict()['top'])
                return (top >= top_bound and top < bottom_bound and
                        tag.name == u'div')
            return False

        df = convert_divs_to_df(soup.find_all(find_divs_within_bounds))
        df['fields_str'] = [str(x) for x in df['fields']]
        df = df.sort_values(['top', 'left'])

        # Charges can be grouped in different sections (e.g., if the gas rate
        # changes in the middle of the month). We only care about the last
        # section, because it contains the Fixed Delivery Charge.
        charges = df[df['left'] > df[df['fields_str'] == "[u'Charges']"]['left']
                    .iloc[0]].iloc[-1]['fields']
        charge_desc = df[df['fields_str'].str.find(' days') >= 0] \
            .iloc[-1]['fields'][1:]
        return dict(zip(charge_desc[-len(charges):], charges))
    except AttributeError as error:
        print("Error scraping gas charges")
    return {}

def get_gas_rates(soup):
    def find_gas_rates(tag):
        return tag.name == u'div' and tag.decode().find(
            'Gas Fixed Delivery Charge') >= 0

    gas_div = soup.find_all(find_gas_rates)[0]
    gas_fields = format_fields(gas_div.contents[0])
    gas_fields = gas_fields[1:]
    gas_rates = format_fields(gas_div.next_sibling.next_sibling.
                              next_sibling.contents[0])
    gas_charges = format_fields(gas_div.next_sibling.next_sibling.
                                next_sibling.next_sibling.contents[0])

    return dict(zip([x + ' Rate' for x in gas_fields
                if (x.find('HST') == -1) and x.find('Fixed') == -1],
                    gas_rates))


def convert_data_to_df(data):
    cols = list(data[0]['summary'].keys())
    if 'Pre-authorized Withdrawal' in cols:
        cols.remove('Pre-authorized Withdrawal')
        cols.append('Total Due')

    for x in data:
        if 'Pre-authorized Withdrawal' in x['summary'].keys():
            x['summary']['Total Due'] = \
                x['summary']['Pre-authorized Withdrawal']
    data_sets = []
    for col in cols:
        data_sets.append([x['summary'][col] for x in data])

    df = pd.DataFrame(data=dict(zip(cols, data_sets)))

    df['Issue Date'] = [str(arrow.get(x, 'MMM DD YYYY').date())
                        for x in df['Issue Date']]
    df = df.set_index('Issue Date')

    # Extract water and gas consumption.
    water_consumption = [np.sum([x['Total Consumption'] if 'Total Consumption' in x
                         else 0 for x in row['water consumption']]) for row in data]
    gas_consumption = [np.sum([x['Total Consumption'] if 'Total Consumption' in x
                       else 0 for x in row['gas consumption']]) for row in data]
    """
    # To do: gas charges were broken when updating to python3
    
    gas_fixed_charge = [x['gas charges']['Gas Fixed Delivery Charge']
                        if 'Gas Fixed Delivery Charge'
                        in x['gas charges'] else None for x in data]
    # Figure out the sales tax rate.
    sales_tax_on_gas = [x['gas charges']['HST on Gas']
                        if 'HST on Gas'
                        in x['gas charges'] else None for x in data]
    sales_tax_rate = df['Gas Charges'] / (
        df['Gas Charges'] - sales_tax_on_gas) - 1

    # Adjust the fixed charge by the sales tax
    df['Gas Fixed Charges'] = np.round(gas_fixed_charge * (
        1 + sales_tax_rate), 2)

    # Calculate the variable charge and rate.
    df['Gas Variable Charges'] = df['Gas Charges'] - df['Gas Fixed Charges']
    df['Gas Variable Rate'] = (df['Gas Variable Charges'] /
                               df['Gas Consumption'])
    """

    df['Water Consumption'] = water_consumption
    df['Gas Consumption'] = gas_consumption
    
    return df


class Timeout(Exception):
    pass


class KitchenerUtilitiesAPI:
    name = get_name()
    
    def __init__(self, user, password, data_directory='.'):
        self._user = user
        self._password = password
        self._driver = None
        self._invoice_list = None
        self._temp_download_dir = tempfile.mkdtemp()
        self._data_directory = data_directory
        self._invoice_directory = None

    def _init_driver(self, headless=False):
        options = webdriver.ChromeOptions()
        prefs = {'download.default_directory' : self._temp_download_dir}
        options.add_experimental_option('prefs', prefs)

        if headless:
            options.add_argument('headless')
            options.add_argument('window-size=1200x600')
            
        self._driver = webdriver.Chrome(options=options)

    def _close_driver(self):
        self._driver.close()
        self._driver = None
        
    def _login(self):
        self._driver.get('https://ebilling.kitchener.ca/sap/bc/ui5_ui5/sap/ZUMCUI5/index.html')
        self._driver.find_element_by_id('__field1').send_keys(self._user)
        self._driver.find_element_by_id('__field0').send_keys(self._password)
        self._driver.find_element_by_id('__button0').click()

    def _get_header_nav_bar(self):
        pages = self._driver.find_element_by_id('headerNavigationBar').find_elements_by_tag_name('li')
        keys = [x.text for x in pages]
        result = dict(zip(keys, pages))
        result.pop('', None)
        return result

    def _get_contracts(self):
        # Pick the account (e.g., "Gas", "Water and Sewer", "Stormwater")
        contract_table = self._driver.find_element_by_id('ContractTable-table').find_element_by_tag_name('tbody')
        rows = contract_table.find_elements_by_tag_name('tr')

        contracts = [x.find_elements_by_tag_name('td')[0] for x in rows]
        keys = [x.text for x in contracts]
        return dict(zip(keys, contracts))


    def _first_page(self, timeout=5):
        # Get a list of the pages available
        t_start = time.time()
        link = None
        while time.time() - t_start < timeout:
            try:
                link = self._driver.find_element_by_id('__table1-paginator--firstPageLink')
                self._driver.execute_script('arguments[0].scrollIntoView(true);', link)
                break
            except NoSuchElementException:
                pass
        if link:
            link.click()
            time.sleep(0.5)
        else:
            raise Timeout
        return

    def _get_pages(self, timeout=5):
        # Get a list of the pages available
        t_start = time.time()
        while time.time() - t_start < timeout:
            try:
                table = self._driver.find_element_by_id('__table1-paginator-pages')
                time.sleep(1)
                break
            except NoSuchElementException:
                pass

        if table:
            time.sleep(0.5)
            pages = table.find_elements_by_tag_name('li')
            keys = [int(x.text) for x in pages]
            return dict(zip(keys, pages))
        else:
            raise Timeout
        return None

    def download_invoices(self, start_date=None, end_date=None, timeout=5):
        if self._invoice_list is not None:
            return self._invoice_list
        
        self._init_driver(headless=False)

        self._invoice_directory = os.path.abspath(os.path.join(self._data_directory,
                                                   self.name,
                                                   'invoices'))
        if not os.path.isdir(self._invoice_directory):
            os.makedirs(self._invoice_directory)
        
        try:
            self._login()

            # convert start and end dates to date objects
            if start_date:
                start_date = arrow.get(start_date).date()
            if end_date:
                end_date = arrow.get(end_date).date()

            def get_data():
                # Iterate through the invoices in reverse chronological order
                # (i.e., newest invoices are first).

                billing_table = self._driver.find_element_by_id('__table1-table')

                rows = [[y for y in x.find_elements_by_tag_name('td')]
                        for x in billing_table.find_element_by_tag_name('tbody'). \
                            find_elements_by_tag_name('tr')]

                data = []
                for row in rows:
                    row_data = [x.text for x in row[1:]]
                    if row_data[0] == '':
                        continue

                    date = arrow.get(row_data[1], 'MM/DD/YYYY').date()

                    if start_date and date < start_date:
                        break

                    if end_date and date > end_date:
                        continue

                    data.append(row_data)
                    new_filepath = os.path.join(self._invoice_directory, 
                        '%s - %s - $%s.pdf' % (date.isoformat(),
                                           self.name,
                                           row_data[3]))

                    def download_link(link, ext, timeout=5):
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
                            files = glob.glob(os.path.join(self._temp_download_dir, '*.%s' % ext))
                            if len(files):
                                filepath = os.path.join(self._temp_download_dir, files[0])
                                time.sleep(0.5)
                                break
                        if not filepath:
                            raise Timeout
                        return filepath

                    if not os.path.exists(new_filepath):
                        # download the pdf invoice
                        for img in row[0].find_elements_by_tag_name('img'):
                            if img.get_property('title') == 'PDF':
                                filepath = download_link(img, 'pdf')
                                os.rename(filepath, new_filepath)

                return data

            self._get_header_nav_bar()['BILLING'].click()
            time.sleep(0.5)

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
                page_data = get_data()
                # If this page returned some data within the date range, add it
                if len(page_data):
                    data += page_data
                # If there was no data within the date range and we alread have data,
                # it means that any remaining pages must be prior to the start date;
                # therefore we should stop.
                elif len(data):
                    break
        finally:
            self._close_driver()

        # Convert to a dictionary
        results = {}
        for i, name in enumerate(['Invoice ID', 'Invoice Date', 'Due Date', 'Invoice Amount']):
            results[name] = [x[i] for x in data]

        # Reformat dates
        for name in ['Invoice Date', 'Due Date']:
            results[name] = [arrow.get(x, 'MM/DD/YYYY').date().isoformat() for x in results[name]]

        self._invoice_list = pd.DataFrame(results)
        
        return self._invoice_list
    
    def get_consumption_history(self, contract, headless=True):
        self._init_driver(headless=headless)

        try:
            def get_data():
                # The Consumption history div (this contains all of the data we are interested in)
                consumption_history = self._driver.find_element_by_id('contractConsumptionHistory'). \
                    find_element_by_id('__table1-table').find_element_by_tag_name('tbody')
                rows = consumption_history.find_elements_by_tag_name('tr')
                data = [[y.text for y in x.find_elements_by_tag_name('td')] for x in rows]
                return data

            self._login()

            self._get_header_nav_bar()['ACCOUNTS'].click()
            self._get_contracts()[contract].click()

            # Click on the "Consumption History" tab
            link = self._driver.find_element_by_id('contractDetailNavigationBarItem2')
            self._driver.execute_script('arguments[0].scrollIntoView(true);', link)
            link.click()
            time.sleep(0.5)

            data = []
            for page in self._get_pages().keys():
                link = self._get_pages()[page]
                self._driver.execute_script('arguments[0].scrollIntoView(true);', link)
                time.sleep(0.5)
                link.click()
                data += get_data()

            # sum values that have the same date
            dates = [x for x, y in data]
            results = dict(zip(dates, [0]*len(dates)))
            results.pop('', None)
            for date, consumption in data:
                if date != '':
                    results[date] += float(consumption)
        finally:
            self._close_driver()

        def convert_to_series(data):
            dates = [arrow.get('%s 01 %s' % tuple(x.split(' ')), 'MMMM DD YYYY').date() for x in list(data.keys())]
            dates = ['%d-%02d-%02d' % (x.year, x.month, calendar.monthrange(x.year, x.month)[1]) for x in dates]    
            return pd.Series(list(data.values()), index=dates)                
        
        return convert_to_series(results)