"""Locked expected downtime and energy-weighted availability equations."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .degradation import DegradedYear


HOURS_PER_YEAR = 8760.0


@dataclass(frozen=True)
class AvailableYear:
    """One annual energy value after the locked availability factor."""

    year: int
    degradation_factor: float
    energy_degraded_kwh: float
    availability_factor: float
    energy_net_kwh: float


@dataclass(frozen=True)
class AvailabilityResult:
    failure_rate_events_per_year: float
    disturbed_fraction: float
    availability_factor: float
    lifetime_availability_ratio: float
    gross_lifetime_energy_kwh: float
    net_lifetime_energy_kwh: float
    annual: tuple[AvailableYear, ...]


def _nonnegative_finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value


def expected_failure_rate(
    equivalent_module_count: float,
    module_failure_rate_per_year: float,
) -> float:
    """Return ``N_module,eq * lambda_module`` in expected events/year."""

    count = _nonnegative_finite("equivalent_module_count", equivalent_module_count)
    rate = _nonnegative_finite(
        "module_failure_rate_per_year", module_failure_rate_per_year
    )
    return count * rate


def expected_availability_factor(
    failure_rate_events_per_year: float,
    downtime_hours_per_event: float,
    disturbed_area_m2_per_event: float,
    bipv_area_m2: float,
    *,
    reversibility_time_factor: float = 1.0,
) -> tuple[float, float]:
    """Return disturbed fraction and clipped expected availability.

    This follows the locked bounded-comparison approximation and is not a
    measured reliability curve.
    """

    failure_rate = _nonnegative_finite(
        "failure_rate_events_per_year", failure_rate_events_per_year
    )
    downtime = _nonnegative_finite(
        "downtime_hours_per_event", downtime_hours_per_event
    )
    disturbed_area = _nonnegative_finite(
        "disturbed_area_m2_per_event", disturbed_area_m2_per_event
    )
    bipv_area = _nonnegative_finite("bipv_area_m2", bipv_area_m2)
    if bipv_area == 0.0:
        raise ValueError("bipv_area_m2 must be greater than zero")
    time_factor = _nonnegative_finite(
        "reversibility_time_factor", reversibility_time_factor
    )
    disturbed_fraction = disturbed_area / bipv_area
    availability = 1.0 - (
        failure_rate
        * downtime
        * time_factor
        * disturbed_fraction
        / HOURS_PER_YEAR
    )
    return disturbed_fraction, min(1.0, max(0.0, availability))


def apply_expected_availability(
    degraded_years: Iterable[DegradedYear],
    *,
    failure_rate_events_per_year: float,
    downtime_hours_per_event: float,
    disturbed_area_m2_per_event: float,
    bipv_area_m2: float,
    reversibility_time_factor: float = 1.0,
) -> AvailabilityResult:
    """Apply the constant expected availability factor to degraded energy."""

    disturbed_fraction, availability_factor = expected_availability_factor(
        failure_rate_events_per_year,
        downtime_hours_per_event,
        disturbed_area_m2_per_event,
        bipv_area_m2,
        reversibility_time_factor=reversibility_time_factor,
    )
    annual = tuple(
        AvailableYear(
            year=item.year,
            degradation_factor=item.factor,
            energy_degraded_kwh=item.energy_kwh,
            availability_factor=availability_factor,
            energy_net_kwh=item.energy_kwh * availability_factor,
        )
        for item in degraded_years
    )
    if not annual:
        raise ValueError("degraded_years must not be empty")
    gross = sum(item.energy_degraded_kwh for item in annual)
    net = sum(item.energy_net_kwh for item in annual)
    lifetime_ratio = net / gross if gross > 0.0 else availability_factor
    return AvailabilityResult(
        failure_rate_events_per_year=float(failure_rate_events_per_year),
        disturbed_fraction=disturbed_fraction,
        availability_factor=availability_factor,
        lifetime_availability_ratio=lifetime_ratio,
        gross_lifetime_energy_kwh=gross,
        net_lifetime_energy_kwh=net,
        annual=annual,
    )


IMPLEMENTATION_STATUS = "IMPLEMENTED_UNIT_TESTED"
