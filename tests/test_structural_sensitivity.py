import math
from pathlib import Path
import unittest

from src.structural_sensitivity import run_energy_structural_sensitivity
from src.structural_sensitivity_qa import evaluate_energy_structural_assertions
from src.weather import load_epw


ROOT = Path(__file__).resolve().parents[1]
EPW = (
    ROOT
    / "data"
    / "weather"
    / "AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw"
)


class EnergyStructuralSensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenarios = run_energy_structural_sensitivity(load_epw(EPW))
        cls.by_id = {item.scenario_id: item for item in cls.scenarios}

    def test_locked_scenarios_execute_in_controlled_order(self):
        self.assertEqual(
            [item.scenario_id for item in self.scenarios],
            ["central", "west_orientation", "equal_temperature_control"],
        )
        self.assertEqual(self.by_id["west_orientation"].input_symbol, "ORI")
        self.assertEqual(
            self.by_id["equal_temperature_control"].input_symbol, "Tcase"
        )

    def test_controlled_energy_regression_values(self):
        expected = {
            "central": {
                "direct": 161751.98052177395,
                "ventilated": 166904.08109413524,
            },
            "west_orientation": {
                "direct": 123308.69932087886,
                "ventilated": 127239.7653102324,
            },
            "equal_temperature_control": {
                "direct": 164328.47048928862,
                "ventilated": 164328.47048928862,
            },
        }
        for scenario_id, mounting_values in expected.items():
            for mounting, value in mounting_values.items():
                self.assertAlmostEqual(
                    self.by_id[scenario_id].first_year_energy_kwh[mounting],
                    value,
                    places=6,
                )

    def test_equal_temperature_control_has_no_mounting_energy_effect(self):
        scenario = self.by_id["equal_temperature_control"]
        self.assertEqual(
            scenario.first_year_energy_kwh["direct"],
            scenario.first_year_energy_kwh["ventilated"],
        )
        for record in scenario.variant_records:
            self.assertEqual(
                record["E1_thermal"],
                scenario.first_year_energy_kwh[str(record["mounting"])],
            )

    def test_pareto_set_robustness_is_explicit(self):
        self.assertEqual(
            self.by_id["central"].pareto.non_dominated_ids,
            ("V02", "V04", "V06", "V08"),
        )
        self.assertEqual(
            self.by_id["west_orientation"].pareto.non_dominated_ids,
            ("V02", "V04", "V06", "V08"),
        )
        self.assertEqual(
            self.by_id["equal_temperature_control"].pareto.non_dominated_ids,
            ("V02", "V04"),
        )
        self.assertEqual(self.by_id["west_orientation"].jaccard_to_central, 1.0)
        self.assertEqual(
            self.by_id["equal_temperature_control"].jaccard_to_central, 0.5
        )

    def test_every_scenario_has_eight_finite_variant_rows(self):
        for scenario in self.scenarios:
            self.assertEqual(len(scenario.variant_records), 8)
            self.assertTrue(
                all(
                    math.isfinite(float(record[field]))
                    for record in scenario.variant_records
                    for field in (
                        "E1_thermal",
                        "E_life",
                        "A_life",
                        "WLC",
                        "CostIntensity_aud_per_kwh",
                        "B_dist",
                        "M",
                        "I",
                        "C",
                        "CIRC",
                    )
                )
            )

    def test_structural_qa_gate_passes(self):
        results = evaluate_energy_structural_assertions(self.scenarios)
        self.assertEqual(
            [item.id for item in results],
            ["ES01", "ES02", "ES03", "ES04", "ES05", "Q14"],
        )
        self.assertTrue(all(item.status == "PASS" for item in results))


if __name__ == "__main__":
    unittest.main()
