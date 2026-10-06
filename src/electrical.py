"""PVWatts DC, locked loss stack, inverter conversion, and integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ElectricalResult:
    p_dc_gross_w: Any
    p_dc_net_w: Any
    p_ac_w: Any
    inverter_dc_limit_w: float


def _runtime():
    try:
        import numpy as np
        import pandas as pd
        import pvlib
    except ImportError as exc:  # pragma: no cover - exercised only before setup
        raise RuntimeError(
            "The energy runtime is not installed. Install requirements.txt first."
        ) from exc
    return np, pd, pvlib


def calculate_electrical_power(
    effective_irradiance: Any,
    temp_cell: Any,
    *,
    pdc0_kwp: float,
    gamma_pdc: float,
    system_loss_fraction: float,
    pac0_kw: float,
    eta_inv_nom: float,
) -> ElectricalResult:
    """Calculate non-negative DC and AC power in watts using locked ordering."""

    np, pd, pvlib = _runtime()
    if not effective_irradiance.index.equals(temp_cell.index):
        raise ValueError("effective-irradiance and temperature indices must match")
    if not 0.0 <= system_loss_fraction < 1.0:
        raise ValueError("system loss fraction must be in [0, 1)")
    if pdc0_kwp <= 0.0 or pac0_kw <= 0.0:
        raise ValueError("DC and AC nominal capacities must be positive")
    if not 0.0 < eta_inv_nom <= 1.0:
        raise ValueError("inverter efficiency must be in (0, 1]")

    p_dc_gross = pvlib.pvsystem.pvwatts_dc(
        effective_irradiance.clip(lower=0.0),
        temp_cell,
        pdc0=pdc0_kwp * 1000.0,
        gamma_pdc=gamma_pdc,
        temp_ref=25.0,
    )
    p_dc_gross = pd.Series(p_dc_gross, index=effective_irradiance.index).clip(lower=0.0)
    p_dc_net = (p_dc_gross * (1.0 - system_loss_fraction)).clip(lower=0.0)

    pac0_w = pac0_kw * 1000.0
    inverter_dc_limit_w = pac0_w / eta_inv_nom
    p_ac = pvlib.inverter.pvwatts(
        p_dc_net,
        pdc0=inverter_dc_limit_w,
        eta_inv_nom=eta_inv_nom,
    )
    p_ac = pd.Series(p_ac, index=effective_irradiance.index).clip(
        lower=0.0, upper=pac0_w
    )
    for name, values in (
        ("gross DC", p_dc_gross),
        ("net DC", p_dc_net),
        ("AC", p_ac),
    ):
        if not np.isfinite(values.to_numpy(dtype=float)).all():
            raise ValueError(f"{name} power contains non-finite values")
    return ElectricalResult(
        p_dc_gross_w=p_dc_gross,
        p_dc_net_w=p_dc_net,
        p_ac_w=p_ac,
        inverter_dc_limit_w=inverter_dc_limit_w,
    )


def integrate_ac_energy_kwh(p_ac_w: Any, timestep_hours: float) -> float:
    """Integrate AC power before failure downtime, returning kWh."""

    np, _, _ = _runtime()
    if timestep_hours <= 0.0:
        raise ValueError("timestep must be positive")
    if (
        not np.isfinite(p_ac_w.to_numpy(dtype=float)).all()
        or (p_ac_w < 0.0).any()
    ):
        raise ValueError("AC power must be finite and non-negative")
    return float(p_ac_w.sum() * timestep_hours / 1000.0)


IMPLEMENTATION_STATUS = "IMPLEMENTED_UNIT_TESTED"
