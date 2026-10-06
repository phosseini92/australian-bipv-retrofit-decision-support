from decimal import Decimal
from dataclasses import replace
import math
import unittest

from src.availability import (
    apply_expected_availability,
    expected_availability_factor,
    expected_failure_rate,
)
from src.config_loader import load_variants
from src.degradation import build_linear_degradation, linear_degradation_factor
from src.input_loader import load_symbol_index
from src.lifecycle_energy import LifecycleParameters, run_lifecycle_energy
from src.lifecycle_qa import evaluate_lifecycle_assertions
from src.replacement import (
    calculate_intervention_burden,
    scheduled_inverter_replacement_years,
)


class LockedLifecycleInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_symbol_index()

    def test_horizon_and_service_life_bounds(self):
        self.assertEqual(self.inputs["T"].central, Decimal("30"))
        self.assertEqual(
            (self.inputs["SL_mod"].low, self.inputs["SL_mod"].central, self.inputs["SL_mod"].high),
            (Decimal("25"), Decimal("30"), Decimal("35")),
        )
        self.assertEqual(self.inputs["SL_inv"].central, Decimal("15"))

    def test_linear_degradation_range(self):
        row = self.inputs["d"]
        self.assertEqual(
            (row.low, row.central, row.high),
            (Decimal("0.005"), Decimal("0.007"), Decimal("0.009")),
        )
        self.assertIn("Linear", row.parameter)

    def test_one_failed_product_is_replaced_per_event(self):
        row = self.inputs["N_replace"]
        self.assertEqual(
            (row.low, row.central, row.high),
            (Decimal("1"), Decimal("1"), Decimal("1")),
        )

    def test_reversibility_has_no_baseline_time_advantage(self):
        self.assertEqual(self.inputs["k_rev,time"].central, Decimal("1"))


class DegradationEquationTests(unittest.TestCase):
    def test_locked_linear_factors(self):
        self.assertEqual(linear_degradation_factor(1, 0.007), 1.0)
        self.assertAlmostEqual(linear_degradation_factor(2, 0.007), 0.993)
        self.assertAlmostEqual(linear_degradation_factor(30, 0.007), 0.797)

    def test_thirty_year_factor_sum_is_linear_not_compound(self):
        annual = build_linear_degradation(1000.0, 30, 0.007)
        expected_factor_sum = 30 - 0.007 * 30 * 29 / 2
        self.assertAlmostEqual(sum(item.factor for item in annual), expected_factor_sum)
        self.assertAlmostEqual(sum(item.energy_kwh for item in annual), 26955.0)
        self.assertNotAlmostEqual(annual[-1].factor, (1.0 - 0.007) ** 29)

    def test_degradation_rejects_invalid_horizon(self):
        with self.assertRaises(ValueError):
            build_linear_degradation(1000.0, 0, 0.007)


class AvailabilityEquationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parameters = LifecycleParameters.from_locked_inputs()

    def test_failure_rate_reproduces_locked_derived_value(self):
        calculated = expected_failure_rate(
            self.parameters.equivalent_module_count,
            self.parameters.module_failure_rate_per_year,
        )
        self.assertAlmostEqual(
            calculated,
            self.parameters.failure_rate_events_per_year,
            places=14,
        )

    def test_disturbed_fraction_and_availability_follow_locked_equation(self):
        disturbed_fraction, availability = expected_availability_factor(
            self.parameters.failure_rate_events_per_year,
            self.parameters.downtime_hours_per_event,
            self.parameters.component_disturbed_area_m2,
            self.parameters.bipv_area_m2,
            reversibility_time_factor=self.parameters.reversibility_time_factor,
        )
        expected_q = (
            self.parameters.component_disturbed_area_m2
            / self.parameters.bipv_area_m2
        )
        expected_availability = 1.0 - (
            self.parameters.failure_rate_events_per_year
            * self.parameters.downtime_hours_per_event
            * expected_q
            / 8760.0
        )
        self.assertAlmostEqual(disturbed_fraction, expected_q)
        self.assertAlmostEqual(availability, expected_availability)

    def test_lifetime_availability_is_energy_weighted_ratio(self):
        degraded = build_linear_degradation(1000.0, 30, 0.007)
        result = apply_expected_availability(
            degraded,
            failure_rate_events_per_year=(
                self.parameters.failure_rate_events_per_year
            ),
            downtime_hours_per_event=self.parameters.downtime_hours_per_event,
            disturbed_area_m2_per_event=(
                self.parameters.assembly_disturbed_area_m2
            ),
            bipv_area_m2=self.parameters.bipv_area_m2,
        )
        self.assertAlmostEqual(
            result.lifetime_availability_ratio,
            result.net_lifetime_energy_kwh / result.gross_lifetime_energy_kwh,
        )
        self.assertAlmostEqual(
            result.lifetime_availability_ratio,
            result.availability_factor,
        )


class ReplacementEquationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parameters = LifecycleParameters.from_locked_inputs()

    def test_module_mass_is_recovered_from_locked_end_of_life_values(self):
        self.assertAlmostEqual(self.parameters.module_mass_kg, 25.5)

    def test_intervention_burden_keeps_adjacent_units_out_of_replaced_mass(self):
        component = calculate_intervention_burden(
            failure_rate_events_per_year=(
                self.parameters.failure_rate_events_per_year
            ),
            horizon_years=self.parameters.horizon_years,
            disturbed_area_m2_per_event=(
                self.parameters.component_disturbed_area_m2
            ),
            handled_module_equivalents_per_event=(
                self.parameters.component_handled_module_equivalents
            ),
            replaced_module_equivalents_per_event=1.0,
            module_mass_kg=self.parameters.module_mass_kg,
        )
        assembly = calculate_intervention_burden(
            failure_rate_events_per_year=(
                self.parameters.failure_rate_events_per_year
            ),
            horizon_years=self.parameters.horizon_years,
            disturbed_area_m2_per_event=(
                self.parameters.assembly_disturbed_area_m2
            ),
            handled_module_equivalents_per_event=(
                self.parameters.assembly_handled_module_equivalents
            ),
            replaced_module_equivalents_per_event=1.0,
            module_mass_kg=self.parameters.module_mass_kg,
        )
        self.assertAlmostEqual(
            component.expected_failure_events,
            self.parameters.locked_expected_failure_events,
        )
        self.assertGreater(
            assembly.handled_scope_burden_module_event,
            component.handled_scope_burden_module_event,
        )
        self.assertAlmostEqual(
            assembly.material_replacement_mass_kg,
            component.material_replacement_mass_kg,
        )

    def test_scheduled_inverter_years_match_locked_horizon_cases(self):
        self.assertEqual(scheduled_inverter_replacement_years(25, 15), (15,))
        self.assertEqual(scheduled_inverter_replacement_years(30, 15), (15,))
        self.assertEqual(
            scheduled_inverter_replacement_years(35, 15),
            (15, 30),
        )


class LifecycleIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parameters = LifecycleParameters.from_locked_inputs()
        cls.results = run_lifecycle_energy(
            load_variants()["variants"],
            {"direct": 161751.98052177395, "ventilated": 166904.08109413524},
            parameters=cls.parameters,
        )

    def test_all_eight_variants_are_propagated(self):
        self.assertEqual(
            [item.variant_id for item in self.results],
            [f"V{i:02d}" for i in range(1, 9)],
        )
        self.assertTrue(
            all(len(item.annual) == self.parameters.horizon_years for item in self.results)
        )

    def test_connection_has_no_baseline_lifecycle_time_advantage(self):
        for mounting in ("direct", "ventilated"):
            for scope in ("assembly_level", "component_level"):
                group = [
                    item
                    for item in self.results
                    if item.mounting == mounting and item.replacement_scope == scope
                ]
                self.assertEqual(len(group), 2)
                self.assertAlmostEqual(
                    group[0].net_lifetime_energy_kwh,
                    group[1].net_lifetime_energy_kwh,
                )

    def test_component_scope_has_higher_availability_than_assembly_scope(self):
        for mounting in ("direct", "ventilated"):
            component = next(
                item
                for item in self.results
                if item.mounting == mounting
                and item.replacement_scope == "component_level"
            )
            assembly = next(
                item
                for item in self.results
                if item.mounting == mounting
                and item.replacement_scope == "assembly_level"
            )
            self.assertGreater(
                component.lifetime_availability_ratio,
                assembly.lifetime_availability_ratio,
            )

    def test_locked_derived_inputs_fail_closed_when_inconsistent(self):
        tampered = replace(
            self.parameters,
            failure_rate_events_per_year=(
                self.parameters.failure_rate_events_per_year + 0.01
            ),
        )
        with self.assertRaises(ValueError):
            tampered.validate_locked_derivations()

    def test_lifecycle_qa_assertions_pass(self):
        qa = evaluate_lifecycle_assertions(self.results, self.parameters)
        self.assertEqual(
            [item.id for item in qa],
            ["Q04", "Q06", "Q07", "Q08", "Q09", "Q14"],
        )
        self.assertTrue(all(item.status == "PASS" for item in qa))

    def test_all_exported_scalars_are_finite(self):
        for result in self.results:
            record = result.as_record()
            for key, value in record.items():
                if isinstance(value, float):
                    self.assertTrue(math.isfinite(value), key)


if __name__ == "__main__":
    unittest.main()
