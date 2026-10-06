"""Mounting-specific SAPM cell temperature and structural control."""

from __future__ import annotations

from typing import Any


DIRECT_PROXY = "close_mount_glass_glass"
VENTILATED_PROXY = "open_rack_glass_glass"


def _runtime():
    try:
        import pandas as pd
        import pvlib
    except ImportError as exc:  # pragma: no cover - exercised only before setup
        raise RuntimeError(
            "The energy runtime is not installed. Install requirements.txt first."
        ) from exc
    return pd, pvlib


def sapm_cell_temperature(
    poa_global: Any,
    temp_air: Any,
    wind_speed: Any,
    *,
    proxy_name: str,
):
    """Resolve the locked named pvlib preset and calculate cell temperature."""

    _, pvlib = _runtime()
    presets = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS["sapm"]
    if proxy_name not in (DIRECT_PROXY, VENTILATED_PROXY):
        raise ValueError(f"unapproved SAPM proxy: {proxy_name!r}")
    parameters = presets[proxy_name]
    return pvlib.temperature.sapm_cell(
        poa_global,
        temp_air,
        wind_speed,
        **parameters,
    )


def calculate_mounting_temperatures(
    poa_global: Any,
    temp_air: Any,
    wind_speed: Any,
    *,
    direct_proxy: str = DIRECT_PROXY,
    ventilated_proxy: str = VENTILATED_PROXY,
):
    """Return direct, ventilated, and arithmetic-mean control series."""

    pd, _ = _runtime()
    direct = sapm_cell_temperature(
        poa_global, temp_air, wind_speed, proxy_name=direct_proxy
    )
    ventilated = sapm_cell_temperature(
        poa_global, temp_air, wind_speed, proxy_name=ventilated_proxy
    )
    result = pd.DataFrame(index=poa_global.index)
    result["temp_cell_direct"] = direct
    result["temp_cell_ventilated"] = ventilated
    result["temp_cell_equal_control"] = (direct + ventilated) / 2.0
    return result


IMPLEMENTATION_STATUS = "IMPLEMENTED_UNIT_TESTED"
