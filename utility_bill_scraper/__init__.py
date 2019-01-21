import os
import subprocess

import pandas as pd
import arrow
from bs4 import BeautifulSoup

def is_number(s):
    """Returns True if string is a number."""
    return s.replace('.','',1).isdigit()


def format_fields(input_list):
    fields = [x.rstrip().strip(':') for x in input_list if x.find('</br>') == -1]
    return [float(x) if is_number(x) else x for x in fields]


def is_kitchener_utilities_bill(soup):
    """Check if this is a Kitchener Utilities bill."""
    def find_kitchener_utilities(tag):
        return tag.name == u'span' and tag.decode().find('Supplier: KITCHENER UTILITIES') >=0
    return len(soup.find_all(find_kitchener_utilities)) > 0


def is_kitchener_wilmot_hydro_bill(soup):
    """Check if this is a Kitchener-Wilmot Hydro bill."""
    def find_kitchener_wilmot_hydro(tag):
        return tag.name == u'span' and tag.decode().find('KITCHENER-WILMOT HYDRO INC') >=0
    return len(soup.find_all(find_kitchener_wilmot_hydro)) > 0

def process_pdf(pdf_file, rename=False, keep_html=False):
    basename, ext = os.path.splitext(pdf_file)
    basepath = os.path.dirname(pdf_file)
    html_file = basename + '.html'
    subprocess.check_output(['python', '%CONDA_PREFIX%\Scripts\pdf2txt.py', '-o%s' % html_file, pdf_file], shell=True)

    with open(html_file, 'r') as f:
        soup = BeautifulSoup(f, 'html.parser')

    if keep_html:
        # re-write formatted html (useful for debugging)
        with open(html_file, 'w') as f:
            f.write(str(soup.prettify().encode('utf-8')))
    else:
        os.remove(html_file)

    result = None

    if (is_kitchener_utilities_bill(soup)):
        import kitchener_utilities as ku
        
        summary = ku.get_summary(soup)

        if 'Pre-authorized Withdrawal' in summary.keys():
            amount_due = summary['Pre-authorized Withdrawal']
        elif 'Total Due' in summary.keys():
            amount_due = summary['Total Due']
        else:
            print("Couldn't find amount due!")
            amount_due = None

        new_name = '%s-Kitchener utilities-$%s.pdf' % (arrow.get(summary['Issue Date'], 'MMM DD YYYY').format('YYYY-MM-DD'),
            amount_due)

        result = {  'name': ku.get_name(),
                    'summary': summary,
                    'water consumption': ku.get_water_consumption(soup),
                    #'water and sewer charges': ku.get_water_and_sewer_charges(soup),
                    'gas consumption': ku.get_gas_consumption(soup),
                    'gas charges': ku.get_gas_charges(soup),
                    'gas rates': ku.get_gas_rates(soup)
                    }
    elif (is_kitchener_wilmot_hydro_bill(soup)):
        import kitchener_wilmot_hydro as kwh

        date = kwh.get_billing_date(soup)
        amount_due = kwh.get_amount_due(soup)
        new_name = '%s-Kitchener-Wilmot hydro-$%s.pdf' % (date, amount_due)
        
        result = {  'name': kwh.get_name(),
                    'date': date,
                    'amount due': amount_due,
                    'electricity rates': kwh.get_electricity_rates(soup),
                    'electricity consumption': kwh.get_electricity_consumption(soup)
                    }
    else:
        print("Unrecognized bill type.")

    if rename:
        os.rename(pdf_file, os.path.join(basepath, new_name))

    return result


def convert_data_to_df(data):
    result = {}

    for x in data:
        if x['name'] not in result.keys():
            result[x['name']] = pd.DataFrame()
        if x['name'] == 'Kitchener Utilities':
            import kitchener_utilities as ku
            df = ku.convert_data_to_df([x])
        elif x['name'] == 'Kitchener-Wilmot Hydro':
            import kitchener_wilmot_hydro as kwh
            df = kwh.convert_data_to_df([x])
        else:
            print('Unknown name.')
            continue
        result[x['name']] = result[x['name']].append(df)
        
    return result