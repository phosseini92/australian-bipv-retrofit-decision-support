from decimal import Decimal
from pathlib import Path
import unittest

import pandas as pd

from src.electrical import calculate_electrical_power, integrate_ac_energy_kwh
from src.input_loader import load_symbol_index
from src.irradiance import (
    POA_AUDIT_COLUMNS,
    apply_physical_iam,
    calculate_poa,
    calculate_solar_geometry,
)
from src.pv_energy import EnergyParameters, run_year_one_energy
from src.temperature import calculate_mounting_temperatures
from src.weather import WeatherDataset, WeatherValidationError, validate_weather_frame


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


class EnergyImplementationTests(unittest.TestCase):
    def setUp(self):
        self.index = pd.date_range(
            "2001-07-01 10:00", periods=3, freq="h", tz="Australia/Melbourne"
        )

    def test_weather_contract_requires_timezone_and_constant_hourly_step(self):
        frame = pd.DataFrame(
            {
                "temp_air": [15.0, 16.0, 17.0],
                "wind_speed": [2.0, 2.0, 2.0],
                "ghi": [100.0, 200.0, 300.0],
                "dni": [50.0, 100.0, 150.0],
                "dhi": [50.0, 100.0, 150.0],
            },
            index=self.index,
        )
        self.assertEqual(validate_weather_frame(frame, expected_hours=3), 1.0)
        naive = frame.copy()
        naive.index = naive.index.tz_localize(None)
        with self.assertRaises(WeatherValidationError):
            validate_weather_frame(naive, expected_hours=3)

    def test_perez_driesse_and_physical_iam_retain_audit_components(self):
        weather = pd.DataFrame(
            {
                "ghi": [200.0, 400.0, 500.0],
                "dni": [300.0, 500.0, 600.0],
                "dhi": [80.0, 120.0, 140.0],
            },
            index=self.index,
        )
        geometry = calculate_solar_geometry(
            self.index,
            {"latitude": -37.817, "longitude": 144.967, "altitude": 31.0},
        )
        poa = calculate_poa(
            weather,
            geometry,
            surface_tilt=90.0,
            surface_azimuth=0.0,
            albedo=0.2,
        )
        self.assertTrue(set(POA_AUDIT_COLUMNS).issubset(poa.columns))
        iam = apply_physical_iam(
            poa,
            geometry,
            surface_tilt=90.0,
            surface_azimuth=0.0,
            refractive_index=1.526,
            extinction_coefficient=4.0,
            glass_thickness=0.0025,
        )
        reconstructed = (
            iam["poa_direct_effective"]
            + iam["poa_sky_effective"]
            + iam["poa_ground_effective"]
        )
        pd.testing.assert_series_equal(
            iam["effective_irradiance"], reconstructed, check_names=False
        )
        self.assertTrue((iam["effective_irradiance"] >= 0.0).all())

    def test_equal_temperature_control_is_hourly_arithmetic_mean(self):
        poa = pd.Series([0.0, 800.0, 1000.0], index=self.index)
        temp_air = pd.Series([15.0, 20.0, 25.0], index=self.index)
        wind = pd.Series([1.0, 2.0, 3.0], index=self.index)
        result = calculate_mounting_temperatures(poa, temp_air, wind)
        expected = (
            result["temp_cell_direct"] + result["temp_cell_ventilated"]
        ) / 2.0
        pd.testing.assert_series_equal(
            result["temp_cell_equal_control"], expected, check_names=False
        )

    def test_loss_order_inverter_limit_clipping_and_energy_units(self):
        irradiance = pd.Series([0.0, 1000.0, 3000.0], index=self.index)
        temperature = pd.Series([25.0, 25.0, 25.0], index=self.index)
        result = calculate_electrical_power(
            irradiance,
            temperature,
            pdc0_kwp=100.0,
            gamma_pdc=-0.0042,
            system_loss_fraction=0.1,
            pac0_kw=50.0,
            eta_inv_nom=0.985,
        )
        self.assertAlmostEqual(result.p_dc_gross_w.iloc[1], 100000.0)
        self.assertAlmostEqual(result.p_dc_net_w.iloc[1], 90000.0)
        self.assertAlmostEqual(result.inverter_dc_limit_w, 50000.0 / 0.985)
        self.assertLessEqual(result.p_ac_w.max(), 50000.0)
        self.assertTrue((result.p_ac_w >= 0.0).all())
        self.assertAlmostEqual(
            integrate_ac_energy_kwh(result.p_ac_w, 1.0),
            result.p_ac_w.sum() / 1000.0,
        )
        with self.assertRaises(ValueError):
            integrate_ac_energy_kwh(pd.Series([float("inf")]), 1.0)

    def test_energy_parameters_are_loaded_from_locked_snapshot(self):
        parameters = EnergyParameters.from_locked_inputs()
        self.assertEqual(parameters.surface_tilt, 90.0)
        self.assertEqual(parameters.pac0_kw, 150.0)
        self.assertEqual(parameters.direct_proxy, "close_mount_glass_glass")
        self.assertEqual(parameters.ventilated_proxy, "open_rack_glass_glass")

    def test_year_one_orchestration_with_zero_irradiance_fixture(self):
        index = pd.date_range(
            "2001-07-01", periods=24, freq="h", tz="Australia/Melbourne"
        )
        frame = pd.DataFrame(
            {
                "temp_air": [15.0] * 24,
                "wind_speed": [2.0] * 24,
                "ghi": [0.0] * 24,
                "dni": [0.0] * 24,
                "dhi": [0.0] * 24,
            },
            index=index,
        )
        dataset = WeatherDataset(
            data=frame,
            metadata={
                "latitude": -37.817,
                "longitude": 144.967,
                "altitude": 31.0,
            },
            timestep_hours=1.0,
            source_path=Path("synthetic-test-only.epw"),
            source_sha256="TEST_ONLY",
        )
        result = run_year_one_energy(
            dataset,
            mounting="direct",
            surface_azimuth=0.0,
        )
        self.assertEqual(result.energy_kwh, 0.0)
        self.assertEqual(len(result.hourly), 24)
        self.assertTrue((result.hourly["p_ac_w"] == 0.0).all())


if __name__ == "__main__":
    unittest.main()
