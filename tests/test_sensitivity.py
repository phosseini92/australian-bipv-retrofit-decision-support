import math
import unittest

from src.config_loader import load_sensitivity, load_variants
from src.lifecycle_cost import CostParameters, run_lifecycle_cost
from src.lifecycle_energy import LifecycleParameters, run_lifecycle_energy
from src.sensitivity import (
    OfatRunDefinition,
    central_numerical_input_vector,
    input_vector_for_run,
    load_ofat_run_definitions,
    parameters_for_run,
    pareto_inclusion_frequencies,
    run_numerical_ofat,
)
from src.sensitivity_qa import evaluate_sensitivity_assertions


FIRST_YEAR_ENERGY = {
    "direct": 161751.98052177395,
    "ventilated": 166904.08109413524,
}


class NumericalOfatContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = load_sensitivity()
        cls.definitions = load_ofat_run_definitions()

    def test_exactly_two_endpoints_for_each_registered_input(self):
        expected = [
            f"{symbol}__{level}"
            for symbol in self.contract["numerical_inputs"]
            for level in ("low", "high")
        ]
        self.assertEqual(len(self.definitions), 24)
        self.assertEqual([item.run_id for item in self.definitions], expected)
        self.assertTrue(
            all(item.source_sheet and item.source_row > 0 for item in self.definitions)
        )

    def test_each_valid_endpoint_changes_only_its_named_input(self):
        central = central_numerical_input_vector()
        unchanged_endpoint = []
        for definition in self.definitions:
            vector = input_vector_for_run(definition)
            changed = [
                symbol for symbol in central if vector[symbol] != central[symbol]
            ]
            if definition.run_id == "V_rec__low":
                self.assertEqual(changed, [])
                unchanged_endpoint.append(definition.run_id)
            else:
                self.assertEqual(changed, [definition.changed_parameter])
        self.assertEqual(unchanged_endpoint, ["V_rec__low"])

    def test_required_manifest_fields_remain_locked(self):
        self.assertEqual(
            self.contract["required_run_manifest_fields"],
            [
                "changed_parameter", "source_row", "value", "variant_set",
                "code_version", "timestamp",
            ],
        )


class NumericalOfatDerivationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.definitions = {
            item.run_id: item for item in load_ofat_run_definitions()
        }

    def test_service_life_changes_horizon_without_module_replacement(self):
        variants = load_variants()["variants"]
        for run_id, horizon, inverter_years in (
            ("SL_mod__low", 25, (15,)),
            ("SL_mod__high", 35, (15, 30)),
        ):
            lifecycle_parameters, cost_parameters = parameters_for_run(
                self.definitions[run_id]
            )
            self.assertEqual(lifecycle_parameters.horizon_years, horizon)
            self.assertEqual(cost_parameters.horizon_years, horizon)
            lifecycle = run_lifecycle_energy(
                variants,
                FIRST_YEAR_ENERGY,
                parameters=lifecycle_parameters,
            )
            costs = run_lifecycle_cost(
                variants,
                lifecycle,
                parameters=cost_parameters,
            )
            self.assertTrue(
                all(item.inverter_replacement_years == inverter_years for item in lifecycle)
            )
            self.assertTrue(
                all(item.inverter_replacement_years == inverter_years for item in costs)
            )
            self.assertTrue(all(len(item.annual) == horizon for item in lifecycle))
            self.assertTrue(all(len(item.annual) == horizon for item in costs))

    def test_failure_rate_endpoint_recomputes_dependent_inputs(self):
        lifecycle, cost = parameters_for_run(self.definitions["λ_mod__high"])
        expected_rate = (
            lifecycle.equivalent_module_count
            * lifecycle.module_failure_rate_per_year
        )
        self.assertAlmostEqual(lifecycle.failure_rate_events_per_year, expected_rate)
        self.assertAlmostEqual(
            lifecycle.locked_expected_failure_events,
            expected_rate * lifecycle.horizon_years,
        )
        self.assertAlmostEqual(cost.failure_rate_events_per_year, expected_rate)

    def test_assembly_handling_endpoint_recomputes_disturbed_area(self):
        central = LifecycleParameters.from_locked_inputs()
        lifecycle, _ = parameters_for_run(self.definitions["N_handle,asm__high"])
        module_area = (
            central.component_disturbed_area_m2
            / central.component_handled_module_equivalents
        )
        self.assertEqual(lifecycle.assembly_handled_module_equivalents, 5.0)
        self.assertAlmostEqual(lifecycle.assembly_disturbed_area_m2, module_area * 5.0)

    def test_cost_endpoints_recompute_all_cached_derivations(self):
        _, bipv = parameters_for_run(self.definitions["C_BIPV__low"])
        self.assertEqual(bipv.direct_mount_cost_per_m2, 381.25)
        self.assertAlmostEqual(
            bipv.ventilated_mount_cost_per_m2,
            bipv.reference_bipv_cost_per_m2
            * (1.0 + bipv.ventilated_complexity_factor),
        )
        self.assertAlmostEqual(
            bipv.reversibility_premium_per_m2,
            bipv.reference_bipv_cost_per_m2 * bipv.reversibility_premium_factor,
        )
        self.assertAlmostEqual(
            bipv.failed_product_material_cost_per_event_aud,
            bipv.module_area_m2 * bipv.reference_bipv_cost_per_m2,
        )

        _, om = parameters_for_run(self.definitions["m_OM__low"])
        self.assertAlmostEqual(
            om.cached_direct_annual_om_aud,
            om.bipv_area_m2 * om.direct_mount_cost_per_m2 * om.annual_om_rate,
        )

        _, recycling = parameters_for_run(self.definitions["C_rec__high"])
        self.assertAlmostEqual(
            recycling.transport_component_aud
            + recycling.processing_component_aud,
            recycling.eol_recycling_cost_aud,
        )

        _, recovery = parameters_for_run(self.definitions["V_rec__high"])
        self.assertAlmostEqual(
            recovery.total_owner_recovery_credit_aud,
            recovery.eol_pv_mass_tonnes
            * recovery.owner_recovery_credit_per_tonne_aud,
        )

    def test_central_cost_parameters_are_not_mutated(self):
        central = CostParameters.from_locked_inputs()
        parameters_for_run(self.definitions["p_vent__high"])
        self.assertEqual(
            central.ventilated_complexity_factor,
            CostParameters.from_locked_inputs().ventilated_complexity_factor,
        )

    def test_unregistered_parameter_fails_closed(self):
        definition = OfatRunDefinition(
            run_id="invented__high",
            changed_parameter="invented",
            level="high",
            value=1.0,
            source_sheet="none",
            source_row=1,
        )
        with self.assertRaises(ValueError):
            parameters_for_run(definition)


class NumericalOfatIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.central_records, cls.central_pareto, cls.results = run_numerical_ofat(
            FIRST_YEAR_ENERGY
        )
        cls.valid_results = [
            item for item in cls.results if item.is_valid_sensitivity_run
        ]

    def test_central_reference_and_run_counts(self):
        self.assertEqual(
            self.central_pareto.non_dominated_ids,
            ("V02", "V04", "V06", "V08"),
        )
        self.assertEqual(len(self.results), 24)
        self.assertEqual(len(self.valid_results), 23)
        excluded = [item for item in self.results if not item.is_valid_sensitivity_run]
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded[0].definition.run_id, "V_rec__low")
        self.assertEqual(excluded[0].exclusion_reason, "locked_endpoint_equals_central")

    def test_p_rev_zero_is_the_only_valid_set_change(self):
        changed = [
            item for item in self.valid_results
            if item.pareto.non_dominated_ids
            != self.central_pareto.non_dominated_ids
        ]
        self.assertEqual([item.definition.run_id for item in changed], ["p_rev__low"])
        self.assertEqual(changed[0].pareto.non_dominated_ids, ("V04", "V08"))
        self.assertEqual(changed[0].jaccard_to_central, 0.5)

    def test_inclusion_frequency_uses_only_valid_runs(self):
        frequencies = pareto_inclusion_frequencies(
            self.results,
            [str(row["id"]) for row in self.central_records],
        )
        self.assertEqual(frequencies["V04"], 1.0)
        self.assertEqual(frequencies["V08"], 1.0)
        self.assertEqual(frequencies["V02"], 22 / 23)
        self.assertEqual(frequencies["V06"], 22 / 23)
        self.assertEqual(frequencies["V01"], 0.0)
        self.assertEqual(frequencies["V03"], 0.0)
        self.assertEqual(frequencies["V05"], 0.0)
        self.assertEqual(frequencies["V07"], 0.0)
        self.assertTrue(all(math.isfinite(value) for value in frequencies.values()))

    def test_every_endpoint_emits_eight_finite_variant_rows(self):
        scalar_fields = (
            "E_life", "A_life", "WLC", "B_dist", "M", "I", "C", "CIRC",
            "CostIntensity_aud_per_kwh",
        )
        for result in self.results:
            self.assertEqual(len(result.variant_records), 8)
            for record in result.variant_records:
                for field in scalar_fields:
                    self.assertTrue(math.isfinite(float(record[field])), field)

    def test_numerical_ofat_qa_passes(self):
        qa = evaluate_sensitivity_assertions(
            self.central_records,
            self.results,
        )
        self.assertEqual(
            [item.id for item in qa],
            ["S01", "Q13", "S02", "S03", "S04", "Q14", "S05"],
        )
        self.assertTrue(all(item.status == "PASS" for item in qa))


if __name__ == "__main__":
    unittest.main()
