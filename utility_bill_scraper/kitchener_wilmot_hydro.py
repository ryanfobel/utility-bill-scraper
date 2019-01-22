import re

import arrow
import numpy as np
import pandas as pd

from utility_bill_scraper import format_fields, is_number


def get_name():
    return 'Kitchener-Wilmot Hydro'


def get_electricity_consumption(soup):
    def find_kWh(tag):
        return tag.name == u'span' and (
            tag.decode().find('kWh Off Peak') >= 0 or
            tag.decode().find('kWh Mid Peak') >= 0 or
            tag.decode().find('kWh On Peak') >= 0)
    fields = []
    for x in soup.find_all(find_kWh):
        fields += format_fields(x)

    data = {'off peak': 0,
            'mid peak': 0,
            'on peak': 0}

    for x in fields:
        if x.find('kWh Off Peak') > 0:
            data['off peak'] += float(x[:x.find('kWh Off Peak')])
        elif x.find('kWh Mid Peak') > 0:
            data['mid peak'] += float(x[:x.find('kWh Mid Peak')])
        elif x.find('kWh On Peak') > 0:
            data['on peak'] += float(x[:x.find('kWh On Peak')])

    return data


def get_billing_date(soup):
    def find_billing(tag):
        return tag.name == u'div' and tag.decode().find('BILLING DATE') >= 0

    match = re.search('([A-Z]+)\s+(\d+)\s+(\d+)',
                      format_fields(soup.find_all(find_billing)[0].
                                    next_sibling.next_sibling.span.
                                    contents)[0])
    month, day, year = match.groups()

    return arrow.get("%s %s %s" % (month, day, year),
                     'MMM DD YYYY').date().isoformat()


def get_electricity_rates(soup):
    def find_kWhOffPeak(tag):
        return tag.name == u'div' and tag.decode().find('kWh Off Peak') >= 0

    tag = soup.find(find_kWhOffPeak)
    match = re.search('top:(?P<top>\d+)px', tag.decode())
    top = match.groups()[0]

    # match all divs with the same top pixel coordinate
    def find_matching_top(tag):
        return tag.name == u'div' and tag.decode().find('top:%spx' % top) >= 0

    for x in soup.find_all(find_matching_top):
        fields = format_fields(x.span)
        if len(fields) > 0 and str(fields[0]).find('at $') == 0:
            rates = [float(x[4:]) for x in fields]
            break

    return dict(zip(['off peak', 'on peak', 'mid peak'], rates))


def get_amount_due(soup):
    def find_new_charges(tag):
        return tag.name == u'div' and tag.decode().find('New Charges') >= 0

    tag = soup.find(find_new_charges)
    match = re.search('top:(?P<top>\d+)px', tag.decode())
    top = float(match.groups()[0])

    def find_left_pos(tag):
        if tag.name == u'div':
            match = re.search('left:(?P<left>\d+)px', tag.decode())
            if match:
                left = float(match.groups()[0])
                return left >= 120 and left <= 132
        return False

    tags = soup.find_all(find_left_pos)

    distance = []
    for tag in tags:
        match = re.search('top:(?P<top>\d+)px', tag.decode())
        distance.append(abs(float(match.groups()[0]) - top))

    amount_due = format_fields(
        tags[np.nonzero(distance == np.min(distance))[0][0]].span)[0]

    index = str(amount_due).find('CR')
    if index >= 0:
        amount_due = (-1) * float(amount_due[:index])

    return amount_due


def convert_data_to_df(data):
    df = pd.DataFrame({'Date': [arrow.get(x['date']).date() for x in data],
                       'Amount Due': [x['amount due'] for x in data],
                       'Off Peak Consumption': [x['electricity consumption']
                                                ['off peak'] for x in data],
                       'Mid Peak Consumption': [x['electricity consumption']
                                                ['mid peak'] for x in data],
                       'On Peak Consumption': [x['electricity consumption']
                                               ['on peak'] for x in data],
                       'Off Peak Rate': [x['electricity rates']
                                         ['off peak'] for x in data],
                       'Mid Peak Rate': [x['electricity rates']
                                         ['mid peak'] for x in data],
                       'On Peak Rate': [x['electricity rates']
                                        ['on peak'] for x in data]})
    df = df.set_index('Date')

    df['Total Consumption'] = df['Off Peak Consumption'] + \
        df['Mid Peak Consumption'] + df['On Peak Consumption']
    return df
