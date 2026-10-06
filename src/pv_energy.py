"""Auditable year-one energy pipeline implementing the locked specification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .electrical import calculate_electrical_power, integrate_ac_energy_kwh
from .input_loader import load_symbol_index
from .irradiance import apply_physical_iam, calculate_poa, calculate_solar_geometry
from .temperature import calculate_mounting_temperatures
from .weather import WeatherDataset


@dataclass(frozen=True)
class EnergyParameters:
    surface_tilt: float
    albedo: float
    refractive_index: float
    extinction_coefficient: float
    glass_thickness: float
    pdc0_kwp: float
    gamma_pdc: float
    system_loss_fraction: float
    pac0_kw: float
    eta_inv_nom: float
    direct_proxy: str
    ventilated_proxy: str

    @classmethod
    def from_locked_inputs(cls) -> "EnergyParameters":
        rows = load_symbol_index()

        def number(symbol: str) -> float:
            value = rows[symbol].central
            if not hasattr(value, "as_tuple"):
                raise TypeError(f"locked input {symbol} is not numeric")
            return float(value)

        return cls(
            surface_tilt=number("β"),
            albedo=number("ρ_g"),
            refractive_index=number("n_IAM"),
            extinction_coefficient=number("K_IAM"),
            glass_thickness=number("L_IAM"),
            pdc0_kwp=number("Pdc0"),
            gamma_pdc=number("γ_Pmax"),
            system_loss_fraction=number("L_sys"),
            pac0_kw=number("Pac0"),
            eta_inv_nom=number("η_inv,max"),
            direct_proxy=str(rows["T_direct"].central),
            ventilated_proxy=str(rows["T_vent"].central),
        )


@dataclass(frozen=True)
class YearOneEnergyResult:
    mounting: str
    surface_azimuth: float
    energy_kwh: float
    hourly: Any
    weather_provenance: dict[str, Any]


def run_year_one_energy(
    weather: WeatherDataset,
    *,
    mounting: str,
    surface_azimuth: float,
    parameters: EnergyParameters | None = None,
) -> YearOneEnergyResult:
    """Run the locked hourly chain without lifecycle failure downtime."""

    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - exercised only before setup
        raise RuntimeError(
            "The energy runtime is not installed. Install requirements.txt first."
        ) from exc

    parameters = parameters or EnergyParameters.from_locked_inputs()
    if mounting not in {"direct", "ventilated", "equal_temperature_control"}:
        raise ValueError(f"unapproved mounting case: {mounting!r}")

    geometry = calculate_solar_geometry(weather.data.index, weather.metadata)
    poa = calculate_poa(
        weather.data,
        geometry,
        surface_tilt=parameters.surface_tilt,
        surface_azimuth=surface_azimuth,
        albedo=parameters.albedo,
    )
    iam = apply_physical_iam(
        poa,
        geometry,
        surface_tilt=parameters.surface_tilt,
        surface_azimuth=surface_azimuth,
        refractive_index=parameters.refractive_index,
        extinction_coefficient=parameters.extinction_coefficient,
        glass_thickness=parameters.glass_thickness,
    )
    temperatures = calculate_mounting_temperatures(
        poa["poa_global"],
        weather.data["temp_air"],
        weather.data["wind_speed"],
        direct_proxy=parameters.direct_proxy,
        ventilated_proxy=parameters.ventilated_proxy,
    )
    temperature_column = {
        "direct": "temp_cell_direct",
        "ventilated": "temp_cell_ventilated",
        "equal_temperature_control": "temp_cell_equal_control",
    }[mounting]
    electrical = calculate_electrical_power(
        iam["effective_irradiance"],
        temperatures[temperature_column],
        pdc0_kwp=parameters.pdc0_kwp,
        gamma_pdc=parameters.gamma_pdc,
        system_loss_fraction=parameters.system_loss_fraction,
        pac0_kw=parameters.pac0_kw,
        eta_inv_nom=parameters.eta_inv_nom,
    )

    hourly = pd.concat(
        [
            weather.data[["ghi", "dni", "dhi", "temp_air", "wind_speed"]],
            geometry,
            poa[["poa_direct", "poa_sky_diffuse", "poa_ground_diffuse", "poa_global"]],
            iam,
            temperatures,
        ],
        axis=1,
    )
    hourly["p_dc_gross_w"] = electrical.p_dc_gross_w
    hourly["p_dc_net_w"] = electrical.p_dc_net_w
    hourly["p_ac_w"] = electrical.p_ac_w
    if weather.source_index is not None:
        if len(weather.source_index) != len(hourly):
            raise ValueError("source and normalized weather indices differ in length")
        hourly["epw_source_timestamp"] = weather.source_index.astype(str).to_numpy()
        hourly["epw_source_year"] = weather.source_index.year.to_numpy()
    energy_kwh = integrate_ac_energy_kwh(electrical.p_ac_w, weather.timestep_hours)
    return YearOneEnergyResult(
        mounting=mounting,
        surface_azimuth=surface_azimuth,
        energy_kwh=energy_kwh,
        hourly=hourly,
        weather_provenance={
            "source_path": str(weather.source_path),
            "source_sha256": weather.source_sha256,
            "normalization": dict(weather.normalization),
        },
    )


IMPLEMENTATION_STATUS = "IMPLEMENTED_CONTROLLED_EPW_VALIDATED"
