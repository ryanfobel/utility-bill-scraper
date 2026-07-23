"""
Backward compatibility wrapper for Kitchener-Wilmot Hydro (now Enova Power).

This module is deprecated. Use enova_power instead.
"""

import warnings
from .enova_power import *

warnings.warn(
    "kitchener_wilmot_hydro module is deprecated. "
    "Kitchener-Wilmot Hydro is now Enova Power. "
    "Please use 'from utility_bill_scraper.canada.on.enova_power import EnovaPowerAPI' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Alias for backward compatibility
KitchenerWilmotHydroAPI = EnovaPowerAPI
