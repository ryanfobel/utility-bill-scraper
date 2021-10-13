import os
import re
import subprocess

import arrow
import pandas as pd
from bs4 import BeautifulSoup


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


from ._version import get_versions

__version__ = get_versions()["version"]
del get_versions
