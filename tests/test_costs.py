from decimal import Decimal
from dataclasses import replace
import math
import unittest

from src.config_loader import load_variants
from src.cost_qa import evaluate_cost_assertions
from src.input_loader import load_symbol_index
from src.lifecycle_cost import (
    CostParameters,
    discount_factor,
    run_lifecycle_cost,
)
from src.lifecycle_energy import LifecycleParameters, run_lifecycle_energy


class LockedCostInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_symbol_index()

    def test_real_discount_rate_range(self):
        row = self.inputs["r"]
        self.assertEqual(
            (row.low, row.central, row.high),
            (Decimal("0.03"), Decimal("0.07"), Decimal("0.1")),
        )

    def test_reversibility_premium_is_structural_test(self):
        row = self.inputs["p_rev"]
        self.assertEqual(row.status, "STRUCTURAL TEST")
        self.assertEqual(row.central, Decimal("0.05"))

    def test_central_owner_recovery_credit_is_zero(self):
        self.assertEqual(self.inputs["V_rec"].central, Decimal("0"))

    def test_recycling_cost_includes_transport(self):
        recycling = self.inputs["C_rec"]
        separate = self.inputs["D_trans_cost"]
        self.assertIn("including transport", recycling.rationale)
        self.assertEqual(separate.central, "Not added in baseline")

    def test_adjacent_handled_units_are_not_material_replacements(self):
        row = self.inputs["C_extra,asm"]
        self.assertEqual(
            (row.low, row.central, row.high),
            (Decimal("0"), Decimal("0"), Decimal("0")),
        )


class DiscountingTests(unittest.TestCase):
    def test_end_of_year_discount_factors(self):
        self.assertEqual(discount_factor(0, 0.07), 1.0)
        self.assertAlmostEqual(discount_factor(1, 0.07), 1 / 1.07)
        self.assertAlmostEqual(discount_factor(30, 0.07), 1 / (1.07**30))

    def test_discount_factor_rejects_invalid_values(self):
        with self.assertRaises(ValueError):
            discount_factor(-1, 0.07)
        with self.assertRaises(ValueError):
            discount_factor(1, -0.01)


class CostParameterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parameters = CostParameters.from_locked_inputs()

    def test_locked_cost_derivations_reconcile(self):
        self.parameters.validate_locked_derivations()
        self.assertAlmostEqual(
            self.parameters.ventilated_mount_cost_per_m2,
            self.parameters.reference_bipv_cost_per_m2
            * (1 + self.parameters.ventilated_complexity_factor),
        )
        self.assertAlmostEqual(
            self.parameters.reversibility_premium_per_m2,
            self.parameters.reference_bipv_cost_per_m2
            * self.parameters.reversibility_premium_factor,
        )

    def test_non_numeric_central_cost_rules_are_explicit(self):
        self.assertEqual(self.parameters.access_input_label, "BREAK-EVEN OUTPUT")
        self.assertEqual(
            self.parameters.removal_input_label,
            "BREAK-EVEN / sensitivity",
        )
        self.assertEqual(
            self.parameters.separate_transport_rule,
            "Not added in baseline",
        )
        self.assertEqual(self.parameters.central_access_cost_per_event_aud, 0.0)
        self.assertEqual(self.parameters.central_eol_removal_cost_aud, 0.0)

    def test_tampered_cached_derivation_fails_closed(self):
        tampered = replace(
            self.parameters,
            eol_recycling_cost_aud=(
                self.parameters.eol_recycling_cost_aud + 1.0
            ),
        )
        with self.assertRaises(ValueError):
            tampered.validate_locked_derivations()


class LifecycleCostIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.variants = load_variants()["variants"]
        cls.lifecycle_parameters = LifecycleParameters.from_locked_inputs()
        cls.cost_parameters = CostParameters.from_locked_inputs()
        cls.lifecycle_results = run_lifecycle_energy(
            cls.variants,
            {
                "direct": 161751.98052177395,
                "ventilated": 166904.08109413524,
            },
            parameters=cls.lifecycle_parameters,
        )
        cls.results = run_lifecycle_cost(
            cls.variants,
            cls.lifecycle_results,
            parameters=cls.cost_parameters,
        )

    def test_all_eight_variants_have_thirty_year_cost_schedules(self):
        self.assertEqual(
            [item.variant_id for item in self.results],
            [f"V{i:02d}" for i in range(1, 9)],
        )
        self.assertTrue(all(len(item.annual) == 30 for item in self.results))

    def test_initial_cost_and_om_follow_variant_factors(self):
        v01 = self.results[0]
        v03 = self.results[2]
        v05 = self.results[4]
        expected_direct = (
            self.cost_parameters.bipv_area_m2
            * self.cost_parameters.direct_mount_cost_per_m2
        )
        expected_rev = (
            self.cost_parameters.bipv_area_m2
            * self.cost_parameters.reversibility_premium_per_m2
        )
        self.assertAlmostEqual(v01.initial_cost_aud, expected_direct)
        self.assertAlmostEqual(
            v03.initial_cost_aud,
            expected_direct + expected_rev,
        )
        self.assertGreater(v05.initial_cost_aud, v01.initial_cost_aud)
        self.assertAlmostEqual(
            v03.annual_om_cost_aud,
            v03.initial_cost_aud * self.cost_parameters.annual_om_rate,
        )

    def test_corrective_material_cost_is_common_and_scope_independent(self):
        expected_annual = (
            self.cost_parameters.failure_rate_events_per_year
            * self.cost_parameters.failed_product_material_cost_per_event_aud
        )
        for item in self.results:
            self.assertAlmostEqual(
                item.replacement.annual_expected_material_cost_aud,
                expected_annual,
            )
            self.assertEqual(
                item.replacement.assembly_extra_material_cost_per_event_aud,
                0.0,
            )

    def test_inverter_allowance_is_common_reference_cost(self):
        expected = (
            self.cost_parameters.inverter_replacement_factor
            * self.cost_parameters.bipv_area_m2
            * self.cost_parameters.reference_bipv_cost_per_m2
        )
        for item in self.results:
            self.assertAlmostEqual(
                item.inverter_reference_cost_per_event_aud,
                expected,
            )
            self.assertEqual(item.inverter_replacement_years, (15,))
        self.assertEqual(
            sum(year.inverter_aud > 0 for year in self.results[0].annual),
            1,
        )

    def test_eol_recycling_is_not_double_counted_with_transport(self):
        parameters = self.cost_parameters
        self.assertAlmostEqual(
            parameters.transport_component_aud
            + parameters.processing_component_aud,
            parameters.eol_recycling_cost_aud,
        )
        for item in self.results:
            self.assertEqual(item.owner_recovery_credit_aud, 0.0)
            self.assertEqual(item.eol_removal_cost_aud, 0.0)
            self.assertAlmostEqual(
                item.eol_net_cost_aud,
                parameters.eol_recycling_cost_aud,
            )

    def test_wlc_reconciles_to_discounted_schedule(self):
        for item in self.results:
            schedule_pv = sum(
                year.discounted_total_aud for year in item.annual
            )
            self.assertAlmostEqual(
                item.whole_life_cost_aud,
                item.initial_cost_aud + schedule_pv,
            )
            self.assertAlmostEqual(
                item.cost_intensity_aud_per_kwh,
                item.whole_life_cost_aud / item.lifetime_energy_kwh,
            )

    def test_replacement_scope_does_not_create_central_wlc_difference(self):
        for mounting in ("direct", "ventilated"):
            for connection in (
                "low_reversibility",
                "reversible_mechanical",
            ):
                group = [
                    item
                    for item in self.results
                    if item.mounting == mounting
                    and item.connection == connection
                ]
                self.assertEqual(len(group), 2)
                self.assertAlmostEqual(
                    group[0].whole_life_cost_aud,
                    group[1].whole_life_cost_aud,
                )
                self.assertNotAlmostEqual(
                    group[0].cost_intensity_aud_per_kwh,
                    group[1].cost_intensity_aud_per_kwh,
                )

    def test_cost_qa_assertions_pass(self):
        qa = evaluate_cost_assertions(self.results, self.cost_parameters)
        self.assertEqual(
            [item.id for item in qa],
            ["C01", "C02", "C03", "C04", "Q08", "Q09", "Q10", "Q14"],
        )
        self.assertTrue(all(item.status == "PASS" for item in qa))

    def test_all_exported_cost_scalars_are_finite(self):
        for result in self.results:
            for key, value in result.as_record().items():
                if isinstance(value, float):
                    self.assertTrue(math.isfinite(value), key)


if __name__ == "__main__":
    unittest.main()
