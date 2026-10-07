"""Locked break-even equations and explicit non-root handling."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Any, Callable, Mapping, Sequence

from scipy.optimize import brentq

from .config_loader import load_variants
from .lifecycle_cost import (
    CostParameters,
    LifecycleCostResult,
    discount_factor,
    run_lifecycle_cost,
)
from .lifecycle_energy import (
    LifecycleEnergyResult,
    LifecycleParameters,
    run_lifecycle_energy,
)


CONNECTION_PAIRS = (
    ("V03_vs_V01", "V03", "V01"),
    ("V04_vs_V02", "V04", "V02"),
    ("V07_vs_V05", "V07", "V05"),
    ("V08_vs_V06", "V08", "V06"),
)
MOUNTING_PAIRS = (
    ("V05_vs_V01", "V05", "V01"),
    ("V06_vs_V02", "V06", "V02"),
    ("V07_vs_V03", "V07", "V03"),
    ("V08_vs_V04", "V08", "V04"),
)
REPLACEMENT_SCOPE_PAIRS = (
    ("V02_vs_V01", "V02", "V01"),
    ("V04_vs_V03", "V04", "V03"),
    ("V06_vs_V05", "V06", "V05"),
    ("V08_vs_V07", "V08", "V07"),
)


@dataclass(frozen=True)
class RootResult:
    status: str
    value: float | None
    lower_bound: float
    upper_bound: float
    function_at_lower: float
    function_at_upper: float
    residual: float | None

    def as_record(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "value": self.value,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "function_at_lower": self.function_at_lower,
            "function_at_upper": self.function_at_upper,
            "residual": self.residual,
        }


@dataclass(frozen=True)
class BreakEvenResult:
    output_id: str
    comparison_id: str
    variant_a: str | None
    variant_b: str | None
    threshold_name: str
    unit: str
    status: str
    value: float | None
    lower_bound: float | None
    upper_bound: float | None
    residual: float | None
    equation: str
    scenario: str
    note: str

    def as_record(self) -> dict[str, Any]:
        return {
            "output_id": self.output_id,
            "comparison_id": self.comparison_id,
            "variant_a": self.variant_a,
            "variant_b": self.variant_b,
            "threshold_name": self.threshold_name,
            "unit": self.unit,
            "status": self.status,
            "value": self.value,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "residual": self.residual,
            "equation": self.equation,
            "scenario": self.scenario,
            "note": self.note,
        }


@dataclass(frozen=True)
class BreakEvenAnalysis:
    maximum_premium: tuple[BreakEvenResult, ...]
    required_access_saving_locked_formula: tuple[BreakEvenResult, ...]
    required_access_saving_wlc_diagnostic: tuple[BreakEvenResult, ...]
    service_life: tuple[BreakEvenResult, ...]
    recovery_value: tuple[BreakEvenResult, ...]
    discount_rate_primary: BreakEvenResult
    discount_rate_candidate_matrix: tuple[BreakEvenResult, ...]
    locked_spec_mismatches: tuple[Mapping[str, Any], ...]

    def all_numeric_results(self) -> tuple[BreakEvenResult, ...]:
        return (
            self.maximum_premium
            + self.required_access_saving_locked_formula
            + self.required_access_saving_wlc_diagnostic
            + self.service_life
            + self.recovery_value
            + self.discount_rate_candidate_matrix
        )

    def as_record(self) -> dict[str, Any]:
        return {
            "maximum_premium": [item.as_record() for item in self.maximum_premium],
            "required_access_saving_locked_formula": [
                item.as_record()
                for item in self.required_access_saving_locked_formula
            ],
            "required_access_saving_wlc_diagnostic": [
                item.as_record()
                for item in self.required_access_saving_wlc_diagnostic
            ],
            "service_life": [item.as_record() for item in self.service_life],
            "recovery_value": [item.as_record() for item in self.recovery_value],
            "discount_rate_primary": self.discount_rate_primary.as_record(),
            "discount_rate_candidate_matrix": [
                item.as_record() for item in self.discount_rate_candidate_matrix
            ],
            "locked_spec_mismatches": list(self.locked_spec_mismatches),
        }


def _finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def bounded_root(
    function: Callable[[float], float],
    lower_bound: float,
    upper_bound: float,
    *,
    value_tolerance: float = 1e-9,
    root_tolerance: float = 1e-12,
) -> RootResult:
    """Solve a bounded sign-change root and report non-roots explicitly."""

    lower = _finite("lower_bound", lower_bound)
    upper = _finite("upper_bound", upper_bound)
    if lower >= upper:
        raise ValueError("root interval must have lower_bound < upper_bound")
    f_lower = _finite("function_at_lower", function(lower))
    f_upper = _finite("function_at_upper", function(upper))
    midpoint = (lower + upper) / 2.0
    f_midpoint = _finite("function_at_midpoint", function(midpoint))
    if all(
        abs(value) <= value_tolerance
        for value in (f_lower, f_midpoint, f_upper)
    ):
        return RootResult(
            "IDENTICALLY_EQUAL_WITHIN_TOLERANCE",
            None,
            lower,
            upper,
            f_lower,
            f_upper,
            None,
        )
    if abs(f_lower) <= value_tolerance:
        return RootResult(
            "ROOT_AT_LOWER_BOUND", lower, lower, upper,
            f_lower, f_upper, f_lower,
        )
    if abs(f_upper) <= value_tolerance:
        return RootResult(
            "ROOT_AT_UPPER_BOUND", upper, lower, upper,
            f_lower, f_upper, f_upper,
        )
    if f_lower * f_upper > 0.0:
        return RootResult(
            "NO_SIGN_CHANGE_WITHIN_BOUND",
            None,
            lower,
            upper,
            f_lower,
            f_upper,
            None,
        )
    root = float(brentq(function, lower, upper, xtol=root_tolerance))
    residual = _finite("root_residual", function(root))
    return RootResult(
        "ROOT_FOUND", root, lower, upper,
        f_lower, f_upper, residual,
    )


def _validate_variants(variants: Sequence[Mapping[str, Any]]) -> None:
    ids = tuple(str(item.get("id")) for item in variants)
    if ids != tuple(f"V{number:02d}" for number in range(1, 9)):
        raise ValueError("break-even analysis requires exact V01–V08 order")


def _costs_by_id(
    variants: Sequence[Mapping[str, Any]],
    lifecycle: Sequence[LifecycleEnergyResult],
    parameters: CostParameters,
) -> dict[str, LifecycleCostResult]:
    return {
        item.variant_id: item
        for item in run_lifecycle_cost(
            variants, lifecycle, parameters=parameters
        )
    }


def _parameters_for_horizon(
    lifecycle_base: LifecycleParameters,
    cost_base: CostParameters,
    horizon_years: int,
) -> tuple[LifecycleParameters, CostParameters]:
    if isinstance(horizon_years, bool) or not isinstance(horizon_years, int):
        raise ValueError("break-even horizon must be an integer")
    if horizon_years < 1:
        raise ValueError("break-even horizon must be positive")
    lifecycle = replace(
        lifecycle_base,
        horizon_years=horizon_years,
        locked_expected_failure_events=(
            lifecycle_base.failure_rate_events_per_year * horizon_years
        ),
    )
    cost = replace(cost_base, horizon_years=horizon_years)
    lifecycle.validate_locked_derivations()
    cost.validate_locked_derivations()
    return lifecycle, cost


def _discounted_event_factor(
    failure_rate_events_per_year: float,
    horizon_years: int,
    real_discount_rate: float,
) -> float:
    factor = failure_rate_events_per_year * sum(
        discount_factor(year, real_discount_rate)
        for year in range(1, horizon_years + 1)
    )
    if not math.isfinite(factor) or factor <= 0.0:
        raise ValueError("discounted event factor must be positive and finite")
    return factor


def _maximum_premium_results(
    cost: CostParameters,
    *,
    downstream_savings_pv_aud: float = 0.0,
) -> tuple[BreakEvenResult, ...]:
    savings = _finite("downstream_savings_pv_aud", downstream_savings_pv_aud)
    if savings < 0.0:
        raise ValueError("downstream savings cannot be negative")
    denominator = cost.bipv_area_m2 * cost.reference_bipv_cost_per_m2
    value = savings / denominator
    status = "ZERO_THRESHOLD" if value == 0.0 else "ROOT_FOUND"
    return tuple(
        BreakEvenResult(
            "BE_rev", comparison_id, reversible, low,
            "maximum_reversibility_premium", "fraction", status, value,
            0.0, None, 0.0,
            "p_rev,max = PV(downstream savings)/(A_BIPV*C_BIPV)",
            "central_no_quantified_downstream_savings",
            "A zero threshold does not assert that reversible design has no benefit; it reflects that no downstream monetary saving is asserted centrally.",
        )
        for comparison_id, reversible, low in CONNECTION_PAIRS
    )


def _access_saving_results(
    cost: CostParameters,
    lifecycle: LifecycleParameters,
    central_costs: Mapping[str, LifecycleCostResult],
    *,
    eol_differential_pv_aud: float = 0.0,
) -> tuple[tuple[BreakEvenResult, ...], tuple[BreakEvenResult, ...]]:
    eol = _finite("eol_differential_pv_aud", eol_differential_pv_aud)
    event_factor = _discounted_event_factor(
        lifecycle.failure_rate_events_per_year,
        lifecycle.horizon_years,
        cost.real_discount_rate,
    )
    initial_premium = (
        cost.bipv_area_m2
        * cost.reference_bipv_cost_per_m2
        * cost.reversibility_premium_factor
    )
    numerator = initial_premium - eol
    locked_value = 0.0 if numerator <= 0.0 else numerator / event_factor
    locked_status = "ZERO_THRESHOLD" if locked_value == 0.0 else "ROOT_FOUND"
    locked_results: list[BreakEvenResult] = []
    diagnostic_results: list[BreakEvenResult] = []
    for comparison_id, reversible, low in CONNECTION_PAIRS:
        wlc_delta = (
            central_costs[reversible].whole_life_cost_aud
            - central_costs[low].whole_life_cost_aud
        )
        wlc_value = max(0.0, (wlc_delta - eol) / event_factor)
        locked_residual = wlc_delta - eol - locked_value * event_factor
        diagnostic_residual = wlc_delta - eol - wlc_value * event_factor
        locked_results.append(BreakEvenResult(
            "BE_access", comparison_id, reversible, low,
            "required_access_saving_locked_formula", "AUD/event",
            locked_status, locked_value, 0.0, None, locked_residual,
            "[A_BIPV*C_BIPV*p_rev - PV(EoL differential)]/[sum(f_fail/(1+r)^y)]",
            "locked_central_premium_and_zero_eol_differential",
            "This is the explicit Section 11.2 equation. Its WLC residual is retained because WLC also makes O&M proportional to premium-inclusive C0.",
        ))
        diagnostic_results.append(BreakEvenResult(
            "BE_access_WLC_diagnostic", comparison_id, reversible, low,
            "required_access_saving_for_full_wlc_equality", "AUD/event",
            "ROOT_FOUND" if wlc_value > 0.0 else "ZERO_THRESHOLD",
            wlc_value, 0.0, None, diagnostic_residual,
            "[WLC_reversible - WLC_low - PV(EoL differential)]/[sum(f_fail/(1+r)^y)]",
            "diagnostic_reconciliation_not_a_replacement_locked_formula",
            "Reported to expose, not silently resolve, the locked access-formula/WLC inconsistency.",
        ))
    return tuple(locked_results), tuple(diagnostic_results)


def _service_life_results(
    variants: Sequence[Mapping[str, Any]],
    first_year_energy_kwh: Mapping[str, float],
    lifecycle_base: LifecycleParameters,
    cost_base: CostParameters,
) -> tuple[BreakEvenResult, ...]:
    costs_by_horizon: dict[int, dict[str, LifecycleCostResult]] = {}
    for horizon in range(10, 51):
        lifecycle_parameters, cost_parameters = _parameters_for_horizon(
            lifecycle_base, cost_base, horizon
        )
        lifecycle = run_lifecycle_energy(
            variants,
            first_year_energy_kwh,
            parameters=lifecycle_parameters,
        )
        costs_by_horizon[horizon] = _costs_by_id(
            variants, lifecycle, cost_parameters
        )

    results: list[BreakEvenResult] = []
    for comparison_id, ventilated, direct in MOUNTING_PAIRS:
        deltas = {
            horizon: (
                costs[ventilated].cost_intensity_aud_per_kwh
                - costs[direct].cost_intensity_aud_per_kwh
            )
            for horizon, costs in costs_by_horizon.items()
        }
        roots = [horizon for horizon, delta in deltas.items() if delta <= 0.0]
        value = float(min(roots)) if roots else None
        results.append(BreakEvenResult(
            "BE_life", comparison_id, ventilated, direct,
            "minimum_service_life_for_ventilated_cost_intensity_parity",
            "years",
            "ROOT_FOUND" if value is not None else "NO_BREAK_EVEN_LE_50_YEARS",
            value, 10.0, 50.0,
            deltas[int(value)] if value is not None else None,
            "minimum integer T where WLC_vent(T)/E_life,vent(T) <= WLC_direct(T)/E_life,direct(T)",
            "central_inputs_with_integer_horizon_search_10_to_50",
            f"Cost-intensity difference is {deltas[10]:.12g} AUD/kWh at T=10 and {deltas[50]:.12g} AUD/kWh at T=50.",
        ))
    return tuple(results)


def _recovery_value_results(
    cost: CostParameters,
    central_costs: Mapping[str, LifecycleCostResult],
) -> tuple[BreakEvenResult, ...]:
    terminal_credit_factor = (
        cost.eol_pv_mass_tonnes
        * discount_factor(cost.horizon_years, cost.real_discount_rate)
    )
    if terminal_credit_factor <= 0.0:
        raise ValueError("terminal recovery-credit factor must be positive")
    results: list[BreakEvenResult] = []
    for comparison_id, reversible, low in CONNECTION_PAIRS:
        wlc_delta = (
            central_costs[reversible].whole_life_cost_aud
            - central_costs[low].whole_life_cost_aud
        )
        value = max(0.0, wlc_delta / terminal_credit_factor)
        residual = wlc_delta - value * terminal_credit_factor
        results.append(BreakEvenResult(
            "BE_rec", comparison_id, reversible, low,
            "incremental_owner_recovery_credit", "AUD/t",
            "ROOT_FOUND" if value > 0.0 else "ZERO_THRESHOLD",
            value, 0.0, None, residual,
            "Delta WLC - Delta V_rec*M_EOL/(1+r)^T = 0",
            "incremental_credit_to_reversible_variant_with_other_differential_savings_zero",
            "An incremental threshold is not a claim that only reversible systems can be recycled.",
        ))
    return tuple(results)


def _discount_rate_candidate_results(
    variants: Sequence[Mapping[str, Any]],
    central_lifecycle: Sequence[LifecycleEnergyResult],
    cost_base: CostParameters,
) -> tuple[BreakEvenResult, ...]:
    pair_groups = (
        ("connection", CONNECTION_PAIRS),
        ("mounting", MOUNTING_PAIRS),
        ("replacement_scope", REPLACEMENT_SCOPE_PAIRS),
    )
    results: list[BreakEvenResult] = []
    for factor, pairs in pair_groups:
        for comparison_id, variant_a, variant_b in pairs:
            def delta(rate: float) -> float:
                parameters = replace(cost_base, real_discount_rate=rate)
                costs = _costs_by_id(variants, central_lifecycle, parameters)
                return (
                    costs[variant_a].whole_life_cost_aud
                    - costs[variant_b].whole_life_cost_aud
                )

            root = bounded_root(delta, 0.0, 0.15)
            results.append(BreakEvenResult(
                "BE_r_candidate", comparison_id, variant_a, variant_b,
                "real_discount_rate", "fraction", root.status, root.value,
                root.lower_bound, root.upper_bound, root.residual,
                "WLC_A(r) - WLC_B(r) = 0",
                f"candidate_one_factor_{factor}_contrast_central_cost_rules",
                f"Endpoint deltas: {root.function_at_lower:.12g} AUD at r=0 and {root.function_at_upper:.12g} AUD at r=0.15.",
            ))
    return tuple(results)


def run_break_even_analysis(
    first_year_energy_kwh: Mapping[str, float],
    *,
    variants: Sequence[Mapping[str, Any]] | None = None,
) -> BreakEvenAnalysis:
    """Evaluate all locked thresholds without inventing a selected rate pair."""

    variants = tuple(variants or load_variants()["variants"])
    _validate_variants(variants)
    lifecycle_base = LifecycleParameters.from_locked_inputs()
    cost_base = CostParameters.from_locked_inputs()
    central_lifecycle = run_lifecycle_energy(
        variants, first_year_energy_kwh, parameters=lifecycle_base
    )
    central_costs = _costs_by_id(variants, central_lifecycle, cost_base)
    access_locked, access_diagnostic = _access_saving_results(
        cost_base, lifecycle_base, central_costs
    )
    primary_discount = BreakEvenResult(
        "BE_r", "not_locked", None, None,
        "real_discount_rate", "fraction",
        "LOCKED_PAIRWISE_COMPARISON_NOT_SPECIFIED", None,
        0.0, 0.15, None,
        "WLC_A(r) - WLC_B(r) = 0",
        "requires_selected_pairwise_comparison",
        "The locked sources define the interval and equation but do not identify A and B; no pair is selected in code.",
    )
    mismatches = (
        {
            "id": "BE-M01",
            "status": "MISMATCH",
            "item": "The explicit BE_access numerator excludes the premium-driven O&M difference even though WLC defines O&M as m_OM*C0.",
        },
        {
            "id": "BE-M02",
            "status": "BLOCKER",
            "item": "BE_r requires a selected pairwise comparison, but no A/B pair is designated in the three locked sources.",
        },
        {
            "id": "BE-M03",
            "status": "MISMATCH",
            "item": "Research Design v2.0 names an intervention-frequency threshold, while the Analysis Specification and Input Table define no corresponding output equation or scenario.",
        },
    )
    return BreakEvenAnalysis(
        maximum_premium=_maximum_premium_results(cost_base),
        required_access_saving_locked_formula=access_locked,
        required_access_saving_wlc_diagnostic=access_diagnostic,
        service_life=_service_life_results(
            variants,
            first_year_energy_kwh,
            lifecycle_base,
            cost_base,
        ),
        recovery_value=_recovery_value_results(cost_base, central_costs),
        discount_rate_primary=primary_discount,
        discount_rate_candidate_matrix=_discount_rate_candidate_results(
            variants, central_lifecycle, cost_base
        ),
        locked_spec_mismatches=mismatches,
    )


IMPLEMENTATION_STATUS = "IMPLEMENTED_BLOCKED_BY_LOCKED_SPEC_CLARIFICATION"
