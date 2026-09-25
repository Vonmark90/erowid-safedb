"""
Unit tests for Database SQLite FTS5 and CRUD operations.
"""

import unittest
import os
from erowid_safedb.db import Database
from erowid_safedb.models import Substance, DosageInfo, DurationInfo, ExperienceReport, ExperienceDoseItem, AdverseEvent
from erowid_safedb.seed_data import seed_database


class TestDatabase(unittest.TestCase):
    TEST_DB = "data/test_db.sqlite"

    def setUp(self):
        if os.path.exists(self.TEST_DB):
            os.remove(self.TEST_DB)
        self.db = Database(self.TEST_DB)

    def tearDown(self):
        if os.path.exists(self.TEST_DB):
            os.remove(self.TEST_DB)

    def test_seed_and_fts_search(self):
        res = seed_database(self.db)
        self.assertGreater(res["substances_seeded"], 0)
        self.assertGreater(res["interactions_seeded"], 0)
        self.assertGreater(res["reports_seeded"], 0)

        # Look up substance
        sub = self.db.get_substance("mdma")
        self.assertIsNotNone(sub)
        self.assertEqual(sub.slug, "mdma")
        self.assertGreater(len(sub.dosages), 0)

        # FTS5 search query
        results = self.db.search_experiences(query="overdose")
        self.assertGreater(len(results), 0)

        # Search by tag
        tag_results = self.db.search_experiences(tag="Hospital")
        self.assertGreater(len(tag_results), 0)

        # Search by symptom
        sym_results = self.db.search_experiences(symptom="hospitalization")
        self.assertGreater(len(sym_results), 0)


if __name__ == "__main__":
    unittest.main()
