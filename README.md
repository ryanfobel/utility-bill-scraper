---
jupyter:
  jupytext:
    formats: ipynb,md
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.13.0
  kernelspec:
    display_name: Python 3
    language: python
    name: python3
---

<!-- #region -->
# Utility bill scraper

[![build](https://github.com/ryanfobel/utility-bill-scraper/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/ryanfobel/utility-bill-scraper/actions/workflows/build.yml)
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/ryanfobel/utility-bill-scraper/main)
[![PyPI version shields.io](https://img.shields.io/pypi/v/utility-bill-scraper.svg)](https://pypi.python.org/pypi/utility-bill-scraper/)

Extract energy usage and carbon footprint from utility websites or pdf bills. Currently, this library supports:

 * [Kitchener Utilities (gas & water)](https://mybinder.org/v2/gh/ryanfobel/utility-bill-scraper/main?labpath=notebooks%2Fcanada%2Fon%2Fkitchener_utilities.ipynb)

# Install

```sh
pip install utility-bill-scraper
```
<!-- #endregion -->

<!-- #region -->
# Get updates

```python
import os
import sys

# Update the path to include the src directory
sys.path.insert(0, os.path.abspath("src"))

import utility_bill_scraper.canada.on.kitchener_utilities as ku

ku_api = ku.KitchenerUtilitiesAPI(username, password)

# Get up to 24 statements (the most recent).
updates = ku_api.update(24)
if updates is not None:
    print(f"{ len(updates) } statements_downloaded")
ku_api.history().tail()
```
![history_tail](notebooks/canada/on/images/history_tail)
<!-- #endregion -->
