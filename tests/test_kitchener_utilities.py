import os
import sys
import tempfile

from dotenv import load_dotenv

load_dotenv()

# add src to the python path
sys.path.insert(0, os.path.abspath("src"))

import utility_bill_scraper.canada.on.kitchener_utilities as ku

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

def test_login():
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
"""


def test_download_statements():
    data_path = tempfile.mkdtemp()

    # Create a Kitchener Utilities API object with your user name and password
    user = os.getenv("KITCHENER_UTILITIES_USER")
    password = os.getenv("KITCHENER_UTILITIES_PASSWORD")
    ku_api = ku.KitchenerUtilitiesAPI(user, password, data_path)
    pdf_files = ku_api.download_statements(max_downloads=1)
    assert len(pdf_files) > 0


# Test google drive history and statement paths
# history_path = "https://drive.google.com/drive/u/0/folders/13ai3ELMsIrhjFGcv2Lqbwzb4sGkEWK-Y"
# statement_path = "https://drive.google.com/drive/u/0/folders/1ANNdGtBWAR6oTalX_h9QxgPjRwlhHQCr"
