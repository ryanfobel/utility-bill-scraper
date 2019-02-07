import re

import arrow
import pandas as pd
import numpy as np

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
    # 'Billing Conversion Multiplier').
    tag = [x for x in div_list if len(format_fields(x.contents[0])) == 3][0]

    # Extract the top pixel coordinate.
    match = re.search('top:(?P<top>\d+)px', tag.decode())
    top = match.groups()[0]

    # Match all divs with the same top pixel coordinate.
    def find_matching_top(tag):
        return tag.name == u'div' and tag.decode().find('top:%spx' % top) >= 0

    divs = [format_fields(x.contents[0]) for x in soup.find_all(
        find_matching_top)]
    return dict(zip(divs[0], divs[2]))


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

    # Find the div containing 4 fields (gas has an extra
    # 'Billing Conversion Multiplier').
    tag = [x for x in div_list if len(format_fields(x.contents[0])) > 3][0]

    # Extract the top pixel coordinate.
    match = re.search('top:(?P<top>\d+)px', tag.decode())
    top = match.groups()[0]

    # Match all divs with the same top pixel coordinate.
    def find_matching_top(tag):
        return tag.name == u'div' and tag.decode().find('top:%spx' % top) >= 0

    divs = [format_fields(x.contents[0]) for x in soup.find_all(
            find_matching_top)]
    return dict(zip(divs[0], divs[2]))


def get_gas_charges(soup):
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
    cols = data[0]['summary'].keys()
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

    df['Issue Date'] = [arrow.get(x, 'MMM DD YYYY').date()
                        for x in df['Issue Date']]
    df = df.set_index('Issue Date')

    # Extract water and gas consumption.
    water_consumption = [x['water consumption']['Total Consumption']
                         if 'Total Consumption' in x['water consumption']
                         else None for x in data]
    gas_consumption = [x['gas consumption']['Total Consumption']
                       if 'Total Consumption' in x['gas consumption']
                       else None for x in data]
    gas_fixed_charge = [x['gas charges']['Gas Fixed Delivery Charge']
                        if 'Gas Fixed Delivery Charge'
                        in x['gas charges'] else None for x in data]

    df['Water Consumption'] = water_consumption
    df['Gas Consumption'] = gas_consumption

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

    return df
