"""Locked corrective and scheduled intervention-burden equations."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class InterventionBurden:
    expected_failure_events: float
    disturbed_area_burden_m2_event: float
    handled_scope_burden_module_event: float
    expected_replaced_module_equivalents: float
    material_replacement_mass_kg: float


def _nonnegative_finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value


def calculate_intervention_burden(
    *,
    failure_rate_events_per_year: float,
    horizon_years: int,
    disturbed_area_m2_per_event: float,
    handled_module_equivalents_per_event: float,
    replaced_module_equivalents_per_event: float,
    module_mass_kg: float,
) -> InterventionBurden:
    """Calculate expected events, disturbance, handling, and replaced mass."""

    if (
        isinstance(horizon_years, bool)
        or not isinstance(horizon_years, int)
        or horizon_years < 1
    ):
        raise ValueError("horizon_years must be a positive integer")
    failure_rate = _nonnegative_finite(
        "failure_rate_events_per_year", failure_rate_events_per_year
    )
    disturbed_area = _nonnegative_finite(
        "disturbed_area_m2_per_event", disturbed_area_m2_per_event
    )
    handled = _nonnegative_finite(
        "handled_module_equivalents_per_event",
        handled_module_equivalents_per_event,
    )
    replaced = _nonnegative_finite(
        "replaced_module_equivalents_per_event",
        replaced_module_equivalents_per_event,
    )
    mass = _nonnegative_finite("module_mass_kg", module_mass_kg)
    expected_events = failure_rate * horizon_years
    expected_replaced = expected_events * replaced
    return InterventionBurden(
        expected_failure_events=expected_events,
        disturbed_area_burden_m2_event=expected_events * disturbed_area,
        handled_scope_burden_module_event=expected_events * handled,
        expected_replaced_module_equivalents=expected_replaced,
        material_replacement_mass_kg=expected_replaced * mass,
    )


def scheduled_inverter_replacement_years(
    horizon_years: int,
    inverter_service_life_years: int,
) -> tuple[int, ...]:
    """Return service-life multiples strictly inside the analysis horizon.

    This reproduces the locked cases: (15,) for T=25 or 30, and (15, 30)
    for T=35. A replacement exactly at the final horizon boundary is excluded.
    """

    for name, value in (
        ("horizon_years", horizon_years),
        ("inverter_service_life_years", inverter_service_life_years),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    return tuple(
        range(
            inverter_service_life_years,
            horizon_years,
            inverter_service_life_years,
        )
    )


IMPLEMENTATION_STATUS = "IMPLEMENTED_UNIT_TESTED"
