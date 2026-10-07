from dataclasses import replace
from decimal import Decimal
import math
import unittest

from src.circularity import CircularityParameters, run_circularity
from src.config_loader import load_variants
from src.evidence_qa import evaluate_evidence_assertions
from src.input_loader import load_symbol_index


class LockedCircularityInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_symbol_index()

    def test_pscf_is_not_a_native_score(self):
        self.assertEqual(self.inputs["PSCF"].central, "No native quantitative score")

    def test_evidence_code_definition_is_locked(self):
        row = self.inputs["E_code"]
        self.assertEqual(row.status, "LOCKED")
        self.assertIn("0 = constrained/gap", row.central)

    def test_mechanistic_profiles_match_locked_table(self):
        expected = {
            "M_LA": Decimal("0.25"),
            "M_LC": Decimal("0.5"),
            "M_RA": Decimal("0.5"),
            "M_RC": Decimal("0.75"),
        }
        for symbol, value in expected.items():
            self.assertEqual(self.inputs[symbol].central, value)

    def test_institutional_and_contextual_values_are_common(self):
        self.assertEqual(self.inputs["I_DIM"].applies_to, "All variants")
        self.assertEqual(self.inputs["C_DIM"].applies_to, "All variants")
        self.assertEqual(self.inputs["I_DIM"].central, Decimal("0.7"))
        self.assertEqual(self.inputs["C_DIM"].central, Decimal("0.5"))


class CircularityParameterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parameters = CircularityParameters.from_locked_inputs()

    def test_locked_item_level_derivations_reconcile(self):
        self.parameters.validate_locked_contract()

    def test_gap_and_constraint_are_distinct(self):
        items = self.parameters.build_items("low_reversibility", "assembly_level")
        states = {item.symbol: item.evidence_state for item in items}
        self.assertEqual(states["M_DFD_DOC"], "GAP")
        self.assertEqual(states["I_TAKE"], "GAP")
        self.assertEqual(states["C_LOG"], "CONSTRAINT")

    def test_cached_tamper_fails_closed(self):
        rows = dict(self.parameters.rows)
        rows["M_LA"] = replace(rows["M_LA"], central=Decimal("0.26"))
        tampered = replace(self.parameters, rows=rows)
        with self.assertRaises(ValueError):
            tampered.validate_locked_contract()


class CircularityIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.variants = load_variants()["variants"]
        cls.parameters = CircularityParameters.from_locked_inputs()
        cls.central = run_circularity(
            cls.variants, parameters=cls.parameters, gap_treatment="zero"
        )
        cls.gap_excluded = run_circularity(
            cls.variants, parameters=cls.parameters, gap_treatment="exclude"
        )

    def test_all_eight_variants_are_emitted(self):
        self.assertEqual(
            [item.variant_id for item in self.central],
            [f"V{i:02d}" for i in range(1, 9)],
        )

    def test_central_profiles_reproduce_locked_values(self):
        expected = {
            "V01": (0.25, 0.7, 0.5, 0.48333333333333334),
            "V02": (0.5, 0.7, 0.5, 0.5666666666666667),
            "V03": (0.5, 0.7, 0.5, 0.5666666666666667),
            "V04": (0.75, 0.7, 0.5, 0.65),
        }
        for item in self.central[:4]:
            values = (item.mechanistic, item.institutional, item.contextual, item.combined)
            for actual, target in zip(values, expected[item.variant_id]):
                self.assertAlmostEqual(actual, target)

    def test_mounting_has_no_evidence_effect(self):
        for direct, ventilated in zip(self.central[:4], self.central[4:]):
            self.assertEqual(direct.connection, ventilated.connection)
            self.assertEqual(direct.replacement_scope, ventilated.replacement_scope)
            self.assertEqual(
                (direct.mechanistic, direct.institutional, direct.contextual, direct.combined),
                (ventilated.mechanistic, ventilated.institutional, ventilated.contextual, ventilated.combined),
            )

    def test_gap_exclusion_recomputes_denominators_from_item_labels(self):
        v01 = self.gap_excluded[0]
        self.assertAlmostEqual(v01.mechanistic, 1 / 3)
        self.assertAlmostEqual(v01.institutional, 0.875)
        self.assertAlmostEqual(v01.contextual, 0.5)
        self.assertAlmostEqual(v01.combined, 0.5694444444444444)
        self.assertEqual(
            {item.symbol for item in v01.items if item.is_gap},
            {"M_DFD_DOC", "I_TAKE"},
        )

    def test_explicit_constraint_remains_in_gap_excluded_denominator(self):
        v01 = self.gap_excluded[0]
        c_log = next(item for item in v01.items if item.symbol == "C_LOG")
        self.assertEqual(c_log.value, 0.0)
        self.assertFalse(c_log.is_gap)
        self.assertEqual(c_log.evidence_state, "CONSTRAINT")
        self.assertAlmostEqual(v01.contextual, (1 + 0.5 + 0.5 + 0) / 4)

    def test_combined_is_unweighted_arithmetic_mean(self):
        for results in (self.central, self.gap_excluded):
            for item in results:
                self.assertAlmostEqual(
                    item.combined,
                    (item.mechanistic + item.institutional + item.contextual) / 3,
                )

    def test_invalid_gap_treatment_fails_closed(self):
        with self.assertRaises(ValueError):
            run_circularity(self.variants, parameters=self.parameters, gap_treatment="drop_zeroes")

    def test_evidence_qa_passes(self):
        qa = evaluate_evidence_assertions(
            self.central, self.gap_excluded, self.parameters
        )
        self.assertEqual(
            [item.id for item in qa], ["E01", "E02", "E03", "Q11", "E04", "Q14"]
        )
        self.assertTrue(all(item.status == "PASS" for item in qa))

    def test_exported_dimensions_are_finite_and_bounded(self):
        for results in (self.central, self.gap_excluded):
            for item in results:
                for value in (
                    item.mechanistic, item.institutional, item.contextual, item.combined
                ):
                    self.assertTrue(math.isfinite(value))
                    self.assertGreaterEqual(value, 0.0)
                    self.assertLessEqual(value, 1.0)


if __name__ == "__main__":
    unittest.main()
