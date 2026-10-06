"""Locked lifecycle-energy orchestration from Analysis Specification v1.0."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

from .availability import AvailableYear, apply_expected_availability, expected_failure_rate
from .degradation import build_linear_degradation
from .input_loader import load_symbol_index
from .replacement import (
    InterventionBurden,
    calculate_intervention_burden,
    scheduled_inverter_replacement_years,
)


@dataclass(frozen=True)
class LifecycleParameters:
    horizon_years: int
    annual_degradation_rate: float
    bipv_area_m2: float
    equivalent_module_count: float
    module_failure_rate_per_year: float
    failure_rate_events_per_year: float
    locked_expected_failure_events: float
    downtime_hours_per_event: float
    replaced_module_equivalents_per_event: float
    component_handled_module_equivalents: float
    assembly_handled_module_equivalents: float
    component_disturbed_area_m2: float
    assembly_disturbed_area_m2: float
    reversibility_time_factor: float
    inverter_service_life_years: int
    module_mass_kg: float

    @classmethod
    def from_locked_inputs(cls) -> "LifecycleParameters":
        rows = load_symbol_index()

        def number(symbol: str) -> float:
            value = rows[symbol].central
            if not hasattr(value, "as_tuple"):
                raise TypeError(f"locked input {symbol} is not numeric")
            result = float(value)
            if not math.isfinite(result):
                raise ValueError(f"locked input {symbol} is not finite")
            return result

        def integer(symbol: str) -> int:
            value = number(symbol)
            if not value.is_integer() or value < 1:
                raise ValueError(f"locked input {symbol} must be a positive integer")
            return int(value)

        equivalent_count = number("N_mod,eq")
        if equivalent_count <= 0.0:
            raise ValueError("locked input N_mod,eq must be greater than zero")
        # M_EOL is a locked derived value whose source formula is
        # N_mod,eq * 25.5 kg / 1000. Recovering the unit mass from those two
        # locked numeric values avoids introducing a separate assumption.
        module_mass_kg = number("M_EOL") * 1000.0 / equivalent_count
        parameters = cls(
            horizon_years=integer("T"),
            annual_degradation_rate=number("d"),
            bipv_area_m2=number("A_BIPV"),
            equivalent_module_count=equivalent_count,
            module_failure_rate_per_year=number("λ_mod"),
            failure_rate_events_per_year=number("f_fail"),
            locked_expected_failure_events=number("N_fail,30"),
            downtime_hours_per_event=number("DT_event"),
            replaced_module_equivalents_per_event=number("N_replace"),
            component_handled_module_equivalents=number("N_handle,cmp"),
            assembly_handled_module_equivalents=number("N_handle,asm"),
            component_disturbed_area_m2=number("A_dist,cmp"),
            assembly_disturbed_area_m2=number("A_dist,asm"),
            reversibility_time_factor=number("k_rev,time"),
            inverter_service_life_years=integer("SL_inv"),
            module_mass_kg=module_mass_kg,
        )
        parameters.validate_locked_derivations()
        return parameters

    def validate_locked_derivations(self, *, tolerance: float = 1e-12) -> None:
        calculated_rate = expected_failure_rate(
            self.equivalent_module_count,
            self.module_failure_rate_per_year,
        )
        if not math.isclose(
            calculated_rate,
            self.failure_rate_events_per_year,
            rel_tol=tolerance,
            abs_tol=tolerance,
        ):
            raise ValueError("locked f_fail does not equal N_mod,eq * lambda_mod")
        calculated_events = calculated_rate * self.horizon_years
        if not math.isclose(
            calculated_events,
            self.locked_expected_failure_events,
            rel_tol=tolerance,
            abs_tol=tolerance,
        ):
            raise ValueError("locked N_fail,30 does not equal f_fail * T")


@dataclass(frozen=True)
class LifecycleEnergyResult:
    variant_id: str
    short_code: str
    mounting: str
    connection: str
    replacement_scope: str
    first_year_energy_kwh: float
    gross_lifetime_energy_kwh: float
    net_lifetime_energy_kwh: float
    lifetime_availability_ratio: float
    annual_availability_factor: float
    disturbed_fraction: float
    intervention: InterventionBurden
    inverter_replacement_years: tuple[int, ...]
    annual: tuple[AvailableYear, ...]

    def as_record(self) -> dict[str, Any]:
        """Return finite scalar metrics for QA and later decision modules."""

        return {
            "id": self.variant_id,
            "short_code": self.short_code,
            "mounting": self.mounting,
            "connection": self.connection,
            "replacement_scope": self.replacement_scope,
            "E1_thermal_kwh": self.first_year_energy_kwh,
            "E_life_gross_kwh": self.gross_lifetime_energy_kwh,
            "E_life_kwh": self.net_lifetime_energy_kwh,
            "A_life": self.lifetime_availability_ratio,
            "A_annual": self.annual_availability_factor,
            "q_disturbed": self.disturbed_fraction,
            "N_fail_expected": self.intervention.expected_failure_events,
            "B_dist_m2_event": (
                self.intervention.disturbed_area_burden_m2_event
            ),
            "B_handle_module_event": (
                self.intervention.handled_scope_burden_module_event
            ),
            "N_replace_expected": (
                self.intervention.expected_replaced_module_equivalents
            ),
            "M_replace_kg": self.intervention.material_replacement_mass_kg,
            "inverter_replacement_years": list(self.inverter_replacement_years),
        }


def _scope_values(
    replacement_scope: str,
    parameters: LifecycleParameters,
) -> tuple[float, float]:
    if replacement_scope == "component_level":
        return (
            parameters.component_handled_module_equivalents,
            parameters.component_disturbed_area_m2,
        )
    if replacement_scope == "assembly_level":
        return (
            parameters.assembly_handled_module_equivalents,
            parameters.assembly_disturbed_area_m2,
        )
    raise ValueError(f"unapproved replacement scope: {replacement_scope!r}")


def run_variant_lifecycle_energy(
    variant: Mapping[str, Any],
    first_year_energy_kwh: float,
    *,
    parameters: LifecycleParameters | None = None,
) -> LifecycleEnergyResult:
    """Propagate E1 through degradation, availability, and burden equations."""

    parameters = parameters or LifecycleParameters.from_locked_inputs()
    parameters.validate_locked_derivations()
    required = {"id", "short_code", "mounting", "connection", "replacement_scope"}
    missing = required - set(variant)
    if missing:
        raise ValueError(f"variant is missing fields: {sorted(missing)}")
    if variant["mounting"] not in {"direct", "ventilated"}:
        raise ValueError(f"unapproved mounting: {variant['mounting']!r}")
    if variant["connection"] not in {
        "low_reversibility",
        "reversible_mechanical",
    }:
        raise ValueError(f"unapproved connection: {variant['connection']!r}")

    handled_scope, disturbed_area = _scope_values(
        str(variant["replacement_scope"]), parameters
    )
    degraded = build_linear_degradation(
        first_year_energy_kwh,
        parameters.horizon_years,
        parameters.annual_degradation_rate,
    )
    availability = apply_expected_availability(
        degraded,
        failure_rate_events_per_year=parameters.failure_rate_events_per_year,
        downtime_hours_per_event=parameters.downtime_hours_per_event,
        disturbed_area_m2_per_event=disturbed_area,
        bipv_area_m2=parameters.bipv_area_m2,
        reversibility_time_factor=parameters.reversibility_time_factor,
    )
    intervention = calculate_intervention_burden(
        failure_rate_events_per_year=parameters.failure_rate_events_per_year,
        horizon_years=parameters.horizon_years,
        disturbed_area_m2_per_event=disturbed_area,
        handled_module_equivalents_per_event=handled_scope,
        replaced_module_equivalents_per_event=(
            parameters.replaced_module_equivalents_per_event
        ),
        module_mass_kg=parameters.module_mass_kg,
    )
    return LifecycleEnergyResult(
        variant_id=str(variant["id"]),
        short_code=str(variant["short_code"]),
        mounting=str(variant["mounting"]),
        connection=str(variant["connection"]),
        replacement_scope=str(variant["replacement_scope"]),
        first_year_energy_kwh=float(first_year_energy_kwh),
        gross_lifetime_energy_kwh=availability.gross_lifetime_energy_kwh,
        net_lifetime_energy_kwh=availability.net_lifetime_energy_kwh,
        lifetime_availability_ratio=availability.lifetime_availability_ratio,
        annual_availability_factor=availability.availability_factor,
        disturbed_fraction=availability.disturbed_fraction,
        intervention=intervention,
        inverter_replacement_years=scheduled_inverter_replacement_years(
            parameters.horizon_years,
            parameters.inverter_service_life_years,
        ),
        annual=availability.annual,
    )


def run_lifecycle_energy(
    variants: Sequence[Mapping[str, Any]],
    first_year_energy_by_mounting: Mapping[str, float],
    *,
    parameters: LifecycleParameters | None = None,
) -> tuple[LifecycleEnergyResult, ...]:
    """Run the locked central lifecycle-energy equations for V01–V08."""

    parameters = parameters or LifecycleParameters.from_locked_inputs()
    results: list[LifecycleEnergyResult] = []
    for variant in variants:
        mounting = str(variant.get("mounting"))
        if mounting not in first_year_energy_by_mounting:
            raise ValueError(f"missing first-year energy for mounting {mounting!r}")
        results.append(
            run_variant_lifecycle_energy(
                variant,
                first_year_energy_by_mounting[mounting],
                parameters=parameters,
            )
        )
    return tuple(results)


IMPLEMENTATION_STATUS = "IMPLEMENTED_INTEGRATION_GATE"
