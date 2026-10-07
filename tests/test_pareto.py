import math
import unittest

from src.circularity import CircularityParameters, run_circularity
from src.config_loader import load_model
from src.config_loader import load_variants
from src.lifecycle_cost import CostParameters, run_lifecycle_cost
from src.lifecycle_energy import LifecycleParameters, run_lifecycle_energy
from src.pareto import (
    Criterion,
    FLOAT_TOLERANCE_ULPS,
    analyze_pareto,
    analyze_structural_robustness,
    dominates,
    jaccard_similarity,
    load_combined_circularity_criteria,
    load_primary_criteria,
)
from src.pareto_qa import evaluate_pareto_assertions
from src.pareto_robustness_qa import evaluate_pareto_robustness_assertions


class ParetoContractTests(unittest.TestCase):
    def test_primary_vector_and_directions(self):
        pareto = load_model()["pareto"]
        self.assertEqual(
            pareto["primary_criteria"],
            [
                {"field": "E_life", "direction": "maximize"},
                {"field": "A_life", "direction": "maximize"},
                {"field": "WLC", "direction": "minimize"},
                {"field": "B_dist", "direction": "minimize"},
                {"field": "M", "direction": "maximize"},
                {"field": "I", "direction": "maximize"},
                {"field": "C", "direction": "maximize"},
            ],
        )

    def test_no_weights_or_normalization(self):
        pareto = load_model()["pareto"]
        self.assertIsNone(pareto["weights"])
        self.assertIsNone(pareto["normalization"])

    def test_combined_circularity_is_a_structural_test(self):
        test = load_model()["pareto"]["criterion_structure_test"]
        self.assertEqual(test["replace"], ["M", "I", "C"])
        self.assertEqual(test["with"], {"field": "CIRC", "direction": "maximize"})


class DominanceUnitTests(unittest.TestCase):
    def setUp(self):
        self.criteria = (
            Criterion("benefit", "maximize"),
            Criterion("cost", "minimize"),
        )

    def test_dominance_requires_no_worse_and_one_strictly_better(self):
        self.assertTrue(
            dominates(
                {"benefit": 2.0, "cost": 1.0},
                {"benefit": 1.0, "cost": 1.0},
                self.criteria,
            )
        )
        self.assertFalse(
            dominates(
                {"benefit": 2.0, "cost": 2.0},
                {"benefit": 1.0, "cost": 1.0},
                self.criteria,
            )
        )
        self.assertFalse(
            dominates(
                {"benefit": 1.0, "cost": 1.0},
                {"benefit": 1.0, "cost": 1.0},
                self.criteria,
            )
        )

    def test_tolerance_is_only_a_few_machine_ulps(self):
        one_ulp_higher = math.nextafter(1.0, math.inf)
        self.assertFalse(
            dominates(
                {"benefit": one_ulp_higher, "cost": 1.0},
                {"benefit": 1.0, "cost": 1.0},
                self.criteria,
                tolerance_ulps=FLOAT_TOLERANCE_ULPS,
            )
        )
        self.assertTrue(
            dominates(
                {"benefit": 1.0 + 1e-10, "cost": 1.0},
                {"benefit": 1.0, "cost": 1.0},
                self.criteria,
                tolerance_ulps=FLOAT_TOLERANCE_ULPS,
            )
        )

    def test_invalid_records_fail_closed(self):
        with self.assertRaises(ValueError):
            analyze_pareto(
                [{"id": "A", "benefit": math.nan, "cost": 1.0}],
                criteria=self.criteria,
            )

    def test_jaccard_is_a_set_comparison(self):
        self.assertEqual(jaccard_similarity(("A", "B"), ("A", "B")), 1.0)
        self.assertEqual(jaccard_similarity(("A", "B"), ("B", "C")), 1 / 3)
        self.assertEqual(jaccard_similarity((), ()), 1.0)
        with self.assertRaises(KeyError):
            analyze_pareto(
                [{"id": "A", "benefit": 1.0}], criteria=self.criteria
            )
        with self.assertRaises(ValueError):
            analyze_pareto(
                [
                    {"id": "A", "benefit": 1.0, "cost": 1.0},
                    {"id": "A", "benefit": 2.0, "cost": 2.0},
                ],
                criteria=self.criteria,
            )


class ParetoIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        variants = load_variants()["variants"]
        lifecycle = run_lifecycle_energy(
            variants,
            {"direct": 161751.98052177395, "ventilated": 166904.08109413524},
            parameters=LifecycleParameters.from_locked_inputs(),
        )
        costs = run_lifecycle_cost(
            variants, lifecycle, parameters=CostParameters.from_locked_inputs()
        )
        evidence = run_circularity(
            variants,
            parameters=CircularityParameters.from_locked_inputs(),
            gap_treatment="zero",
        )
        gap_excluded_evidence = run_circularity(
            variants,
            parameters=CircularityParameters.from_locked_inputs(),
            gap_treatment="exclude",
        )
        cls.records = []
        cls.gap_excluded_records = []
        for variant, life, cost, circ, gap_circ in zip(
            variants, lifecycle, costs, evidence, gap_excluded_evidence
        ):
            common = {
                **variant,
                "E_life": life.net_lifetime_energy_kwh,
                "A_life": life.lifetime_availability_ratio,
                "WLC": cost.whole_life_cost_aud,
                "B_dist": life.intervention.disturbed_area_burden_m2_event,
            }
            cls.records.append({
                **common,
                "M": circ.mechanistic,
                "I": circ.institutional,
                "C": circ.contextual,
                "CIRC": circ.combined,
            })
            cls.gap_excluded_records.append({
                **common,
                "M": gap_circ.mechanistic,
                "I": gap_circ.institutional,
                "C": gap_circ.contextual,
                "CIRC": gap_circ.combined,
            })
        cls.analysis = analyze_pareto(
            cls.records, criteria=load_primary_criteria()
        )
        cls.robustness = analyze_structural_robustness(
            cls.records, cls.gap_excluded_records
        )

    def test_primary_non_dominated_set(self):
        self.assertEqual(
            self.analysis.non_dominated_ids,
            ("V02", "V04", "V06", "V08"),
        )

    def test_exact_central_dominance_edges(self):
        self.assertEqual(
            {(item.dominator, item.dominated) for item in self.analysis.dominance_pairs},
            {
                ("V02", "V01"), ("V02", "V03"), ("V04", "V03"),
                ("V06", "V05"), ("V06", "V07"), ("V08", "V07"),
            },
        )

    def test_constant_criteria_are_retained_without_fabricated_differences(self):
        self.assertEqual(len({row["I"] for row in self.records}), 1)
        self.assertEqual(len({row["C"] for row in self.records}), 1)
        self.assertEqual(
            [item.field for item in self.analysis.criteria][-2:], ["I", "C"]
        )

    def test_pareto_qa_passes(self):
        qa = evaluate_pareto_assertions(self.records, self.analysis)
        self.assertEqual(
            [item.id for item in qa], ["D01", "D02", "D03", "D04", "Q12", "Q14"]
        )
        self.assertTrue(all(item.status == "PASS" for item in qa))

    def test_combined_criteria_replace_exactly_three_dimensions(self):
        self.assertEqual(
            [(item.field, item.direction) for item in load_combined_circularity_criteria()],
            [
                ("E_life", "maximize"), ("A_life", "maximize"),
                ("WLC", "minimize"), ("B_dist", "minimize"),
                ("CIRC", "maximize"),
            ],
        )

    def test_full_structural_matrix_is_stable(self):
        self.assertEqual(
            [item.scenario_id for item in self.robustness],
            [
                "primary_gap_zero", "combined_gap_zero",
                "primary_gap_excluded", "combined_gap_excluded",
            ],
        )
        for scenario in self.robustness:
            self.assertEqual(
                scenario.analysis.non_dominated_ids,
                ("V02", "V04", "V06", "V08"),
            )
            self.assertEqual(scenario.jaccard_to_central_primary, 1.0)

    def test_gap_treatment_does_not_change_non_evidence_metrics(self):
        for central, excluded in zip(self.records, self.gap_excluded_records):
            for field in ("E_life", "A_life", "WLC", "B_dist"):
                self.assertEqual(central[field], excluded[field])
            self.assertGreater(excluded["CIRC"], central["CIRC"])

    def test_robustness_qa_passes(self):
        qa = evaluate_pareto_robustness_assertions(
            self.records, self.gap_excluded_records, self.robustness
        )
        self.assertEqual(
            [item.id for item in qa],
            ["RB01", "RB02", "RB03", "RB04", "Q12", "Q14"],
        )
        self.assertTrue(all(item.status == "PASS" for item in qa))


if __name__ == "__main__":
    unittest.main()
