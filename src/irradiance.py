"""Solar geometry, Perez-Driesse POA irradiance, and physical IAM."""

from __future__ import annotations

from typing import Any


POA_AUDIT_COLUMNS = (
    "poa_direct",
    "poa_sky_diffuse",
    "poa_ground_diffuse",
    "poa_global",
)


def _runtime():
    try:
        import pandas as pd
        import pvlib
    except ImportError as exc:  # pragma: no cover - exercised only before setup
        raise RuntimeError(
            "The energy runtime is not installed. Install requirements.txt first."
        ) from exc
    return pd, pvlib


def calculate_solar_geometry(index: Any, metadata: dict[str, Any]):
    """Calculate solar position, extraterrestrial DNI, and relative airmass."""

    pd, pvlib = _runtime()
    required = ("latitude", "longitude", "altitude")
    missing = [key for key in required if key not in metadata]
    if missing:
        raise ValueError(f"EPW metadata missing: {missing}")

    solar = pvlib.solarposition.get_solarposition(
        index,
        latitude=float(metadata["latitude"]),
        longitude=float(metadata["longitude"]),
        altitude=float(metadata["altitude"]),
    )
    result = pd.DataFrame(index=index)
    result["solar_zenith"] = solar["apparent_zenith"]
    result["solar_azimuth"] = solar["azimuth"]
    result["dni_extra"] = pvlib.irradiance.get_extra_radiation(index)
    result["airmass_relative"] = pvlib.atmosphere.get_relative_airmass(
        solar["apparent_zenith"]
    )
    return result


def calculate_poa(
    weather: Any,
    geometry: Any,
    *,
    surface_tilt: float,
    surface_azimuth: float,
    albedo: float,
):
    """Calculate audited POA components using locked Perez-Driesse settings."""

    pd, pvlib = _runtime()
    if not weather.index.equals(geometry.index):
        raise ValueError("weather and solar-geometry indices must match")
    result = pvlib.irradiance.get_total_irradiance(
        surface_tilt=surface_tilt,
        surface_azimuth=surface_azimuth,
        solar_zenith=geometry["solar_zenith"],
        solar_azimuth=geometry["solar_azimuth"],
        dni=weather["dni"].clip(lower=0.0),
        ghi=weather["ghi"].clip(lower=0.0),
        dhi=weather["dhi"].clip(lower=0.0),
        dni_extra=geometry["dni_extra"],
        airmass=geometry["airmass_relative"],
        albedo=albedo,
        model="perez-driesse",
    )
    result = pd.DataFrame(result, index=weather.index)
    result.loc[:, list(POA_AUDIT_COLUMNS)] = result.loc[
        :, list(POA_AUDIT_COLUMNS)
    ].clip(lower=0.0)
    return result


def apply_physical_iam(
    poa: Any,
    geometry: Any,
    *,
    surface_tilt: float,
    surface_azimuth: float,
    refractive_index: float,
    extinction_coefficient: float,
    glass_thickness: float,
):
    """Apply beam and Marion diffuse IAM and return audit-ready components."""

    pd, pvlib = _runtime()
    if not poa.index.equals(geometry.index):
        raise ValueError("POA and solar-geometry indices must match")

    aoi = pvlib.irradiance.aoi(
        surface_tilt,
        surface_azimuth,
        geometry["solar_zenith"],
        geometry["solar_azimuth"],
    )
    iam_beam = pvlib.iam.physical(
        aoi,
        n=refractive_index,
        K=extinction_coefficient,
        L=glass_thickness,
    )
    diffuse = pvlib.iam.marion_diffuse(
        "physical",
        surface_tilt,
        n=refractive_index,
        K=extinction_coefficient,
        L=glass_thickness,
    )

    result = pd.DataFrame(index=poa.index)
    result["aoi"] = aoi
    result["iam_beam"] = pd.Series(iam_beam, index=poa.index).fillna(0.0).clip(0.0, 1.0)
    result["iam_sky"] = float(diffuse["sky"])
    result["iam_ground"] = float(diffuse["ground"])
    result["iam_horizon"] = float(diffuse["horizon"])
    result["poa_direct_effective"] = poa["poa_direct"] * result["iam_beam"]
    result["poa_sky_effective"] = poa["poa_sky_diffuse"] * result["iam_sky"]
    result["poa_ground_effective"] = (
        poa["poa_ground_diffuse"] * result["iam_ground"]
    )
    result["effective_irradiance"] = result[
        ["poa_direct_effective", "poa_sky_effective", "poa_ground_effective"]
    ].sum(axis=1).clip(lower=0.0)
    return result


IMPLEMENTATION_STATUS = "IMPLEMENTED_UNIT_TESTED"
