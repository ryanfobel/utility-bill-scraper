import os

# io.open is needed for projects that support Python 2.7
# It ensures open() defaults to text mode with universal newlines,
# and accepts an argument to specify the text encoding
# Python 3 only projects can skip this import
from io import open

from setuptools import find_packages, setup

import versioneer

here = os.path.abspath(os.path.dirname(__file__))

# Get the long description from the README file
with open(os.path.join(here, "README.md"), encoding="utf-8") as f:
    long_description = f.read()


setup(
    name="utility_bill_scraper",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    description="Extract utility usage from pdfs, website scrapers, etc.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords="utility gas electricity hydro water selenium pdfminer",
    author="Ryan Fobel",
    author_email="ryan@fobel.net",
    url="https://github.com/ryanfobel/utility-bill-scraper",
    install_requires=[
        "arrow",
        "beautifulsoup4",
        "numpy",
        "pandas",
        "pdfminer",
        "selenium",
    ],
    license="BSD-3",
)
