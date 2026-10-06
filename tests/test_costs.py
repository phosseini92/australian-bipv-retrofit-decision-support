from decimal import Decimal
import unittest

from src.input_loader import load_symbol_index


class LockedCostInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_symbol_index()

    def test_real_discount_rate_range(self):
        row = self.inputs["r"]
        self.assertEqual((row.low, row.central, row.high), (Decimal("0.03"), Decimal("0.07"), Decimal("0.1")))

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
        self.assertEqual((row.low, row.central, row.high), (Decimal("0"), Decimal("0"), Decimal("0")))


if __name__ == "__main__":
    unittest.main()
