from pathlib import Path
import unittest

from src.baseline import CONTRAST_METRICS, run_formal_baseline
from src.weather import load_epw


ROOT = Path(__file__).resolve().parents[1]
EPW = (
    ROOT
    / "data"
    / "weather"
    / "AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw"
)


class FormalBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis = run_formal_baseline(load_epw(EPW))

    def test_central_rows_and_pareto_set(self):
        self.assertEqual(
            [str(item["id"]) for item in self.analysis.central_records],
            [f"V{index:02d}" for index in range(1, 9)],
        )
        self.assertEqual(
            self.analysis.primary_pareto.non_dominated_ids,
            ("V02", "V04", "V06", "V08"),
        )

    def test_all_registered_sensitivity_families_are_present(self):
        self.assertEqual(len(self.analysis.numerical_ofat), 24)
        self.assertEqual(
            [item.scenario_id for item in self.analysis.energy_structural],
            ["central", "west_orientation", "equal_temperature_control"],
        )
        self.assertEqual(len(self.analysis.circularity_robustness), 4)
        self.assertEqual(len(self.analysis.gap_excluded_records), 8)

    def test_factor_contrasts_are_complete_and_direct(self):
        self.assertEqual(len(self.analysis.factor_contrasts), 12)
        self.assertEqual(
            {item["factor"] for item in self.analysis.factor_contrasts},
            {"mounting", "connection", "replacement_scope"},
        )
        self.assertTrue(all(
            f"delta_{metric}" in row
            for row in self.analysis.factor_contrasts
            for metric in CONTRAST_METRICS
        ))

    def test_cc002_is_primary_and_no_open_issue_remains(self):
        self.assertAlmostEqual(
            self.analysis.break_even.required_access_saving_primary_wlc[0].value,
            14886.976594658823,
        )
        self.assertFalse(self.analysis.break_even.open_locked_spec_issues)

    def test_every_parent_gate_passes_before_export(self):
        self.assertEqual(len(self.analysis.qa_by_gate), 9)
        self.assertTrue(all(
            item["status"] == "PASS"
            for results in self.analysis.qa_by_gate.values()
            for item in results
        ))


if __name__ == "__main__":
    unittest.main()
