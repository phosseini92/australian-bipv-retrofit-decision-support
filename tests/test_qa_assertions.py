from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from src.config_loader import load_model, load_qa_assertions


ROOT = Path(__file__).resolve().parents[1]


class QaContractTests(unittest.TestCase):
    def test_locked_module_contract_is_present(self):
        required = {
            "irradiance.py",
            "temperature.py",
            "electrical.py",
            "lifecycle_energy.py",
            "lifecycle_cost.py",
            "circularity.py",
            "pareto.py",
            "break_even.py",
            "sensitivity.py",
            "baseline.py",
        }
        self.assertTrue(required.issubset({path.name for path in (ROOT / "src").glob("*.py")}))

    def test_all_locked_assertion_ids_are_registered(self):
        config = load_qa_assertions()
        self.assertEqual(config["failure_action"], "hard_fail")
        self.assertEqual(
            [item["id"] for item in config["assertions"]],
            [f"Q{i:02d}" for i in range(1, 15)],
        )
        self.assertTrue(all(item["text"] for item in config["assertions"]))

    def test_mandatory_pipeline_has_all_sixteen_steps(self):
        steps = load_model()["execution_order"]
        self.assertEqual(len(steps), 16)
        self.assertEqual(steps[0], "load_and_validate_locked_inputs_and_manifest")
        self.assertEqual(steps[-1], "run_qa_then_export_tables_figures_and_manifest")

    def test_baseline_is_enabled_only_after_cc002_and_all_gates(self):
        model = load_model()
        self.assertTrue(model["simulation_enabled"])
        self.assertEqual(
            model["status"],
            "ALL_IMPLEMENTATION_GATES_PASSED_BASELINE_ENABLED",
        )
        self.assertEqual(
            model["module_status"]["break_even"],
            "gate_passed_cc002_d1_b_d2_a_d3_a",
        )
        self.assertEqual(
            model["module_status"]["sensitivity"],
            "numerical_ofat_and_energy_structural_gates_passed",
        )

    def test_unimplemented_standalone_exports_remain_fail_closed(self):
        for runner in ("run_sensitivity.py", "run_break_even.py", "run_pareto.py"):
            completed = subprocess.run(
                [sys.executable, str(ROOT / "analysis" / runner)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0, runner)
            self.assertIn("simulation is intentionally disabled", completed.stderr + completed.stdout)


if __name__ == "__main__":
    unittest.main()
