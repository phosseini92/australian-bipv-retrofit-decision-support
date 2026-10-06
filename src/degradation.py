"""Locked linear lifetime-degradation equations."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class DegradedYear:
    """One annual value from the locked linear degradation sequence."""

    year: int
    factor: float
    energy_kwh: float


def _nonnegative_finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value


def linear_degradation_factor(year: int, annual_rate: float) -> float:
    """Return ``max(0, 1 - d*(y-1))`` from the locked specification."""

    if isinstance(year, bool) or not isinstance(year, int) or year < 1:
        raise ValueError("year must be a positive integer")
    annual_rate = _nonnegative_finite("annual_rate", annual_rate)
    return max(0.0, 1.0 - annual_rate * (year - 1))


def build_linear_degradation(
    first_year_energy_kwh: float,
    horizon_years: int,
    annual_rate: float,
) -> tuple[DegradedYear, ...]:
    """Build the annual pre-availability energy sequence for years 1..T."""

    first_year_energy_kwh = _nonnegative_finite(
        "first_year_energy_kwh", first_year_energy_kwh
    )
    if (
        isinstance(horizon_years, bool)
        or not isinstance(horizon_years, int)
        or horizon_years < 1
    ):
        raise ValueError("horizon_years must be a positive integer")
    annual_rate = _nonnegative_finite("annual_rate", annual_rate)
    return tuple(
        DegradedYear(
            year=year,
            factor=linear_degradation_factor(year, annual_rate),
            energy_kwh=(
                first_year_energy_kwh
                * linear_degradation_factor(year, annual_rate)
            ),
        )
        for year in range(1, horizon_years + 1)
    )


IMPLEMENTATION_STATUS = "IMPLEMENTED_UNIT_TESTED"
