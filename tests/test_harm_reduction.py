"""
Unit tests for Harm Reduction Evaluation & Dosage Safety Checker.
"""

import unittest
import os
from erowid_safedb.db import Database
from erowid_safedb.harm_reduction import HarmReductionEngine
from erowid_safedb.seed_data import seed_database


class TestHarmReduction(unittest.TestCase):
    TEST_DB = "data/test_hr.sqlite"

    def setUp(self):
        if os.path.exists(self.TEST_DB):
            os.remove(self.TEST_DB)
        self.db = Database(self.TEST_DB)
        seed_database(self.db)
        self.engine = HarmReductionEngine(self.db)

    def tearDown(self):
        if os.path.exists(self.TEST_DB):
            os.remove(self.TEST_DB)

    def test_evaluate_combination_deadly(self):
        # Alcohol + Alprazolam (Xanax)
        res = self.engine.evaluate_combination(["alcohol", "alprazolam"])
        self.assertEqual(res["overall_risk"], "DEADLY")
        self.assertTrue(res["is_emergency_risk"])
        self.assertGreater(len(res["interactions"]), 0)

    def test_evaluate_combination_synergy_and_fallbacks(self):
        # MDMA + Tramadol (Serotonin Syndrome)
        res = self.engine.evaluate_combination(["mdma", "tramadol"])
        self.assertEqual(res["overall_risk"], "DEADLY")

    def test_evaluate_dosage_safe_and_overdose(self):
        # MDMA: 100mg is typical/common
        res_normal = self.engine.evaluate_dosage("mdma", 100.0)
        self.assertTrue(res_normal.get("found"))
        self.assertIn("COMMON", res_normal["status"])

        # MDMA: 250mg is heavy/overdose hazard
        res_high = self.engine.evaluate_dosage("mdma", 250.0)
        self.assertTrue(res_high.get("found"))
        self.assertIn("HEAVY", res_high["status"])
        self.assertEqual(res_high["risk_flag"], "DANGEROUS")

        # Unknown substance
        res_unknown = self.engine.evaluate_dosage("nonexistent_xyz", 50.0)
        self.assertFalse(res_unknown.get("found"))


if __name__ == "__main__":
    unittest.main()
