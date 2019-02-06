# Utility bill scraper for extracting energy usage from pdfs

Extract data from a series of monthly utility bills. Currently, this library
supports:

 * [Kitchener Utilities (gas & water)](https://www.kitchenerutilities.ca)
 * [Kitchener-Wilmot Hydro (electricity)](https://www.kwhydro.on.ca)

# Setup

The following instructions assume that you have
[Anaconda](https://www.anaconda.com/distribution/) or
[Miniconda](https://docs.conda.io/en/latest/miniconda.html) installed.

```
conda create -n utility-bill-scraper python=2.7
activate utility-bill-scraper
conda config --env --add channels conda-forge
conda install arrow beautifulsoup4 jupyter jupytext matplotlib numpy pandas pdfminer
```