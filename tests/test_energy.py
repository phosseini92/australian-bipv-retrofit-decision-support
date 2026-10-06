from decimal import Decimal
import unittest

from src.input_loader import load_symbol_index


class LockedEnergyInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_symbol_index()

    def test_geometry_and_orientation_controls(self):
        self.assertEqual(self.inputs["β"].central, Decimal("90"))
        self.assertEqual(self.inputs["γ_N"].central, Decimal("0"))
        self.assertEqual(self.inputs["γ_W"].central, Decimal("270"))
        self.assertEqual(self.inputs["ρ_g"].central, Decimal("0.2"))

    def test_irradiance_and_iam_controls(self):
        self.assertEqual(self.inputs["IRR"].central, "Perez-Driesse")
        self.assertEqual(self.inputs["IAM"].central, "pvlib physical IAM")
        self.assertEqual(self.inputs["n_IAM"].central, Decimal("1.526"))
        self.assertEqual(self.inputs["K_IAM"].central, Decimal("4"))
        self.assertEqual(self.inputs["L_IAM"].central, Decimal("0.0025"))

    def test_mounting_specific_temperature_proxies_remain_provisional(self):
        direct = self.inputs["T_direct"]
        ventilated = self.inputs["T_vent"]
        self.assertEqual(direct.central, "close_mount_glass_glass")
        self.assertEqual(ventilated.central, "open_rack_glass_glass")
        self.assertEqual(direct.status, "PROVISIONAL")
        self.assertEqual(ventilated.status, "PROVISIONAL")

    def test_no_double_counted_age_or_availability_loss(self):
        self.assertEqual(self.inputs["L_age"].central, Decimal("0"))
        self.assertEqual(self.inputs["L_avail"].central, Decimal("0"))


if __name__ == "__main__":
    unittest.main()
