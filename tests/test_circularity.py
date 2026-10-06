from decimal import Decimal
import unittest

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


if __name__ == "__main__":
    unittest.main()
