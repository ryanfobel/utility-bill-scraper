import sys
import os

# add src to the python path
sys.path.insert(0, os.path.abspath("src"))

# Test importing the module
import utility_bill_scraper.kitchener_utilities as ku


def test_instantiate_api_class():
    data_directory = os.path.abspath(os.path.join("..", "data"))

    # Create a Kitchener Utilities API object with your user name and password
    from credentials import user, password

    ku_api = ku.KitchenerUtilitiesAPI(user[ku.get_name()], password[ku.get_name()], data_directory)


def test_download_invoices():
    data_directory = os.path.abspath(os.path.join("..", "data"))

    # Create a Kitchener Utilities API object with your user name and password
    from credentials import user, password

    ku_api = ku.KitchenerUtilitiesAPI(user[ku.get_name()], password[ku.get_name()], data_directory)

    invoices = ku_api.download_invoices(start_date="2021-09-01")
    assert len(invoices) > 0
