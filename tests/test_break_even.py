import math
import unittest

from src.break_even import (
    CONNECTION_PAIRS,
    MOUNTING_PAIRS,
    REPLACEMENT_SCOPE_PAIRS,
    bounded_root,
    run_break_even_analysis,
)
from src.break_even_qa import evaluate_break_even_assertions
from src.input_loader import load_symbol_index


FIRST_YEAR_ENERGY = {
    "direct": 161751.98052177395,
    "ventilated": 166904.08109413524,
}


class RootSolverTests(unittest.TestCase):
    def test_sign_change_root_is_solved(self):
        result = bounded_root(lambda value: value - 0.25, 0.0, 1.0)
        self.assertEqual(result.status, "ROOT_FOUND")
        self.assertAlmostEqual(result.value, 0.25)
        self.assertAlmostEqual(result.residual, 0.0)

    def test_non_root_is_explicit(self):
        result = bounded_root(lambda value: value + 1.0, 0.0, 1.0)
        self.assertEqual(result.status, "NO_SIGN_CHANGE_WITHIN_BOUND")
        self.assertIsNone(result.value)

    def test_identically_equal_interval_is_not_a_unique_root(self):
        result = bounded_root(lambda value: 0.0, 0.0, 0.15)
        self.assertEqual(result.status, "IDENTICALLY_EQUAL_WITHIN_TOLERANCE")
        self.assertIsNone(result.value)


class BreakEvenContractTests(unittest.TestCase):
    def test_locked_matched_pairs(self):
        self.assertEqual(
            CONNECTION_PAIRS,
            (
                ("V03_vs_V01", "V03", "V01"),
                ("V04_vs_V02", "V04", "V02"),
                ("V07_vs_V05", "V07", "V05"),
                ("V08_vs_V06", "V08", "V06"),
            ),
        )
        self.assertEqual(len(MOUNTING_PAIRS), 4)
        self.assertEqual(len(REPLACEMENT_SCOPE_PAIRS), 4)

    def test_unsupported_market_tariffs_remain_threshold_labels(self):
        rows = load_symbol_index()
        self.assertEqual(rows["C_access"].central, "BREAK-EVEN OUTPUT")
        self.assertEqual(rows["C_EOL,rem"].central, "BREAK-EVEN / sensitivity")


class BreakEvenIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis = run_break_even_analysis(FIRST_YEAR_ENERGY)

    def test_central_maximum_premium_is_zero_without_asserted_savings(self):
        self.assertTrue(
            all(item.value == 0.0 for item in self.analysis.maximum_premium)
        )

    def test_cc002_d1_b_makes_full_wlc_threshold_primary(self):
        primary = self.analysis.required_access_saving_primary_wlc[0]
        diagnostic = (
            self.analysis
            .required_access_saving_initial_premium_diagnostic[0]
        )
        self.assertAlmostEqual(primary.value, 14886.976594658823)
        self.assertAlmostEqual(diagnostic.value, 14017.27206310166)
        self.assertAlmostEqual(primary.residual, 0.0)
        self.assertAlmostEqual(diagnostic.residual, 1708.8980865952362)

    def test_no_service_life_break_even_is_reported_explicitly(self):
        for item in self.analysis.service_life:
            self.assertEqual(item.status, "NO_BREAK_EVEN_LE_50_YEARS")
            self.assertIsNone(item.value)
            self.assertIn("T=10", item.note)
            self.assertIn("T=50", item.note)

    def test_incremental_recovery_threshold_reconciles(self):
        for item in self.analysis.recovery_value:
            self.assertAlmostEqual(item.value, 18794.47552573408)
            self.assertAlmostEqual(item.residual, 0.0)

    def test_cc002_d2_a_uses_all_four_connection_pairs(self):
        self.assertEqual(
            [item.comparison_id for item in self.analysis.discount_rate_primary],
            ["V03_vs_V01", "V04_vs_V02", "V07_vs_V05", "V08_vs_V06"],
        )
        self.assertTrue(all(
            item.status == "NO_SIGN_CHANGE_WITHIN_BOUND"
            and item.value is None
            for item in self.analysis.discount_rate_primary
        ))
        statuses = [
            item.status for item in self.analysis.discount_rate_candidate_matrix
        ]
        self.assertEqual(statuses.count("NO_SIGN_CHANGE_WITHIN_BOUND"), 8)
        self.assertEqual(
            statuses.count("IDENTICALLY_EQUAL_WITHIN_TOLERANCE"), 4
        )

    def test_non_roots_are_null_not_nan(self):
        for item in self.analysis.all_numeric_results():
            if item.value is not None:
                self.assertTrue(math.isfinite(item.value))
            if item.status.startswith("NO_") or item.status.startswith("IDENTICALLY_"):
                self.assertIsNone(item.value)

    def test_break_even_qa_passes_with_cc002_fully_implemented(self):
        qa = evaluate_break_even_assertions(self.analysis)
        self.assertEqual(
            [item.id for item in qa],
            ["BE01", "BE02", "BE03", "BE04", "BE05", "BE06", "BE07", "Q14"],
        )
        self.assertTrue(all(item.status == "PASS" for item in qa))
        self.assertEqual(
            [item["decision"] for item in self.analysis.cc002_approval],
            ["D1-B", "D2-A", "D3-A"],
        )
        self.assertFalse(self.analysis.open_locked_spec_issues)


if __name__ == "__main__":
    unittest.main()
