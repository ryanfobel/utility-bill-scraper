import sys
import os
import glob
import datetime as dt

from dotenv import load_dotenv

load_dotenv()

# add src to the python path
sys.path.insert(0, os.path.abspath("src"))

import utility_bill_scraper.kitchener_utilities as ku
from utility_bill_scraper import process_pdf

"""
def test_instantiate_api_class():
    data_directory = os.path.abspath(os.path.join("..", "data"))

    # Create a Kitchener Utilities API object with your user name and password
    user = os.getenv("KITCHENER_UTILITIES_USER")
    password = os.getenv("KITCHENER_UTILITIES_PASSWORD")
    ku.KitchenerUtilitiesAPI(user, password, data_directory)

def test_init_driver():
    data_directory = os.path.abspath(os.path.join("..", "data"))

    # Create a Kitchener Utilities API object with your user name and password
    user = os.getenv("KITCHENER_UTILITIES_USER")
    password = os.getenv("KITCHENER_UTILITIES_PASSWORD")
    api = ku.KitchenerUtilitiesAPI(user, password, data_directory)
    api._init_driver()

def test_login_driver():
    data_directory = os.path.abspath(os.path.join("..", "data"))

    # Create a Kitchener Utilities API object with your user name and password
    user = os.getenv("KITCHENER_UTILITIES_USER")
    password = os.getenv("KITCHENER_UTILITIES_PASSWORD")
    api = ku.KitchenerUtilitiesAPI(user, password, data_directory)
    api._init_driver()
    api._login()

def test_get_header_nav_bar():
    data_directory = os.path.abspath(os.path.join("..", "data"))

    # Create a Kitchener Utilities API object with your user name and password
    user = os.getenv("KITCHENER_UTILITIES_USER")
    password = os.getenv("KITCHENER_UTILITIES_PASSWORD")
    api = ku.KitchenerUtilitiesAPI(user, password, data_directory)
    api._init_driver()
    api._login()
    api._get_header_nav_bar()["BILLING"].click()

def test_download_invoices():
    data_directory = os.path.abspath(os.path.join("..", "data"))

    # Create a Kitchener Utilities API object with your user name and password
    user = os.getenv("KITCHENER_UTILITIES_USER")
    password = os.getenv("KITCHENER_UTILITIES_PASSWORD")
    ku_api = ku.KitchenerUtilitiesAPI(user, password, data_directory)

    import datetime as dt
    start_date = (dt.datetime.now().date() - dt.timedelta(weeks=8)).isoformat()
    invoices = ku_api.download_invoices(start_date=start_date)
    assert len(invoices) > 0
"""


def test_process_pdf():
    data_directory = os.path.abspath(os.path.join("..", "data"))

    # Create a Kitchener Utilities API object with your user name and password
    user = os.getenv("KITCHENER_UTILITIES_USER")
    password = os.getenv("KITCHENER_UTILITIES_PASSWORD")
    ku_api = ku.KitchenerUtilitiesAPI(user, password, data_directory)
    start_date = (dt.datetime.now().date() - dt.timedelta(weeks=8)).isoformat()
    invoices = ku_api.download_invoices(start_date=start_date)
    # assert len(invoices) > 0

    pdf_file = glob.glob(ku_api._invoice_directory + "\\" + "*")[-1]
    result = process_pdf(pdf_file, rename=True)
    print(result)
