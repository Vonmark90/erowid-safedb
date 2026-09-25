"""
Unit tests for Erowid Master Catalog, Report Indexing, and Harvester.
"""

import unittest
import os
from erowid_safedb.db import Database
from erowid_safedb.models import CatalogEntry, ReportIndexItem
from erowid_safedb.scraper import ErowidScraper, decode_http_response


class TestCatalogAndHarvester(unittest.TestCase):
    TEST_DB = "data/test_catalog.sqlite"

    def setUp(self):
        if os.path.exists(self.TEST_DB):
            os.remove(self.TEST_DB)
        self.db = Database(self.TEST_DB)
        self.scraper = ErowidScraper(cache_dir="data/cache/test_exp")

    def tearDown(self):
        if os.path.exists(self.TEST_DB):
            os.remove(self.TEST_DB)

    def test_catalog_crud_and_search(self):
        entry = CatalogEntry(
            slug="2cb",
            name="2C-B",
            description="Nexus; 4-Bromo-2,5-dimethoxyphenethylamine",
            synonyms=["Nexus", "Bees"],
            master_url="subs/exp_2CB.shtml",
            categories={"General": "subs/exp_2CB_General.shtml", "Health Problems": "subs/exp_2CB_Health_Problems.shtml"},
            vault_url="/chemicals/2cb/2cb.shtml",
            total_reports=100
        )
        self.db.save_catalog_entry(entry)

        # Lookup by slug
        found = self.db.get_catalog_entry("2cb")
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "2C-B")
        self.assertIn("General", found.categories)

        # Lookup by synonym
        by_syn = self.db.get_catalog_entry("nexus")
        self.assertIsNotNone(by_syn)
        self.assertEqual(by_syn.slug, "2cb")

        # Search query
        search_res = self.db.search_catalog("bromo")
        self.assertEqual(len(search_res), 1)
        self.assertEqual(search_res[0]["slug"], "2cb")

    def test_report_index_items_and_queue(self):
        items = [
            ReportIndexItem(id=101, substance_slug="2cb", category="General"),
            ReportIndexItem(id=102, substance_slug="2cb", category="Health Problems"),
            ReportIndexItem(id=103, substance_slug="mdma", category="Bad Trips"),
        ]
        count = self.db.save_report_index_items(items)
        self.assertEqual(count, 3)

        # Retrieve unscraped
        unscraped_2cb = self.db.get_unscraped_reports(substance_slug="2cb")
        self.assertEqual(len(unscraped_2cb), 2)

        # Mark scraped
        self.db.mark_report_scraped(101)
        remaining = self.db.get_unscraped_reports(substance_slug="2cb")
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].id, 102)

    def test_decode_http_response_gzip(self):
        import gzip
        test_str = "<html><body>Hello Erowid Archive</body></html>"
        gz_bytes = gzip.compress(test_str.encode("utf-8"))
        decoded = decode_http_response(gz_bytes)
        self.assertEqual(decoded, test_str)


if __name__ == "__main__":
    unittest.main()
