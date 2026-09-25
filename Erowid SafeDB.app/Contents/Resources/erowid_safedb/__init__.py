"""
Erowid SafeDB - Systematic Harm Reduction & Drug Education Database.
"""

from erowid_safedb.models import Substance, DosageInfo, DurationInfo, DrugInteraction, ExperienceReport
from erowid_safedb.db import Database
from erowid_safedb.harm_reduction import HarmReductionEngine
from erowid_safedb.scraper import ErowidScraper

__version__ = "1.0.0"
__all__ = [
    "Substance",
    "DosageInfo",
    "DurationInfo",
    "DrugInteraction",
    "ExperienceReport",
    "Database",
    "HarmReductionEngine",
    "ErowidScraper"
]
