from decimal import Decimal
import unittest

from src.input_loader import load_symbol_index


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
        self.assertEqual((row.low, row.central, row.high), (Decimal("0.005"), Decimal("0.007"), Decimal("0.009")))
        self.assertIn("Linear", row.parameter)

    def test_one_failed_product_is_replaced_per_event(self):
        row = self.inputs["N_replace"]
        self.assertEqual((row.low, row.central, row.high), (Decimal("1"), Decimal("1"), Decimal("1")))

    def test_reversibility_has_no_baseline_time_advantage(self):
        self.assertEqual(self.inputs["k_rev,time"].central, Decimal("1"))


if __name__ == "__main__":
    unittest.main()
