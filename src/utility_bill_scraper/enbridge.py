import re

import arrow
import pandas as pd

from utility_bill_scraper import format_fields


def get_name():
    return "Enbridge"


def get_bill_date(soup):
    def find_bill_date(tag):
        return tag.name == u"div" and tag.decode().find("Bill Date") >= 0

    return format_fields(soup.find(find_bill_date).contents[1].contents)[0]


def get_amount_due(soup):
    pos_re = (
        "left:(?P<left>\d+)px.*top:(?P<top>\d+)px.*"
        "width:(?P<width>\d+)px.*height:(?P<height>\d+)"
    )

    def find_amount_due_now(tag):
        return tag.name == u"div" and tag.decode().find("Amount due now") >= 0

    tag = soup.find_all(find_amount_due_now)[-1]
    pos = re.search(pos_re, tag.decode()).groupdict()
    pos = {k: int(v) for (k, v) in pos.items()}
    pos["bottom"] = pos["top"] + pos["height"]
    pos["right"] = pos["left"] + pos["width"]

    def find_divs_on_same_line(tag):
        if tag.name == u"div":
            match = re.search(pos_re, tag.decode())
            if match:
                top = int(match.groupdict()["top"])
                bottom = top + int(match.groupdict()["height"])
                left = int(match.groupdict()["left"])
                left + int(match.groupdict()["width"])
                return (left > pos["right"]) and (
                    (top >= pos["top"] and top <= pos["bottom"])
                    or (bottom >= pos["top"] and bottom <= pos["bottom"])
                )
        return False

    return format_fields(soup.find(find_divs_on_same_line).span.contents)[0][1:]


def get_summary(soup):
    def find_gas_used_this_period(tag):
        return tag.name == u"div" and tag.decode().find("Gas used this period") >= 0

    div = soup.find(find_gas_used_this_period)

    field_data = format_fields(div.next_sibling.span.contents)

    """
    field_names = [format_fields(x.contents) for x in div.contents]

    # Flatten the list of lists.
    field_names = [item for sublist in field_names for item in sublist]
    """

    # Dynamic discovery of field names failing. Hard-code for now.
    field_names = [
        u"Meter Number",
        u"Estimated Reading",
        u"Previous Reading",
        u"Gas used this period",
        u"PEF Value",
        u"Adjusted volume",
    ]

    summary_dict = dict(zip(field_names, field_data))
    summary_dict[u"Bill Date"] = get_bill_date(soup)
    summary_dict[u"Amount Due"] = get_amount_due(soup)

    return summary_dict


def convert_data_to_df(data):
    cols = data[0]["summary"].keys()
    data_sets = []
    for col in cols:
        data_sets.append([x["summary"][col] for x in data])
    df = pd.DataFrame(data=dict(zip(cols, data_sets)))

    df["Bill Date"] = [arrow.get(x, "MMM DD, YYYY").date() for x in df["Bill Date"]]
    df = df.set_index("Bill Date")

    return df
