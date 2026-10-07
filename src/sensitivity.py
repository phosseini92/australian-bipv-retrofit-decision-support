"""Locked numerical one-factor-at-a-time sensitivity orchestration."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Any, Mapping, Sequence

from .circularity import CircularityParameters, run_circularity
from .config_loader import load_sensitivity, load_variants
from .input_loader import InputRow, load_symbol_index
from .lifecycle_cost import CostParameters, run_lifecycle_cost
from .lifecycle_energy import LifecycleParameters, run_lifecycle_energy
from .pareto import (
    FLOAT_TOLERANCE_ULPS,
    ParetoAnalysis,
    analyze_pareto,
    jaccard_similarity,
    load_primary_criteria,
)


SUPPORTED_NUMERICAL_INPUTS = frozenset({
    "d", "SL_mod", "λ_mod", "DT_event", "N_handle,asm", "m_OM",
    "C_BIPV", "p_vent", "p_rev", "r", "C_rec", "V_rec",
})


@dataclass(frozen=True)
class OfatRunDefinition:
    run_id: str
    changed_parameter: str
    level: str
    value: float
    source_sheet: str
    source_row: int


@dataclass(frozen=True)
class OfatRunResult:
    definition: OfatRunDefinition
    input_vector: Mapping[str, float]
    variant_records: tuple[Mapping[str, Any], ...]
    pareto: ParetoAnalysis
    jaccard_to_central: float
    is_valid_sensitivity_run: bool
    exclusion_reason: str | None

    def summary_record(self) -> dict[str, Any]:
        return {
            "run_id": self.definition.run_id,
            "changed_parameter": self.definition.changed_parameter,
            "level": self.definition.level,
            "source_sheet": self.definition.source_sheet,
            "source_row": self.definition.source_row,
            "value": self.definition.value,
            "non_dominated_set": list(self.pareto.non_dominated_ids),
            "jaccard_to_central": self.jaccard_to_central,
            "is_valid_sensitivity_run": self.is_valid_sensitivity_run,
            "exclusion_reason": self.exclusion_reason,
        }


def _numeric_endpoint(row: InputRow, endpoint: str) -> float:
    value = getattr(row, endpoint)
    if not hasattr(value, "as_tuple"):
        raise TypeError(f"{row.symbol} {endpoint} sensitivity value is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{row.symbol} {endpoint} sensitivity value is not finite")
    return result


def load_ofat_run_definitions() -> tuple[OfatRunDefinition, ...]:
    """Return two locked low/high runs for each registered numerical input."""

    contract = load_sensitivity()
    if contract["execution_rule"] != "OFAT":
        raise ValueError("numerical sensitivity execution rule changed")
    registered = tuple(contract["numerical_inputs"])
    if len(registered) != len(set(registered)):
        raise ValueError("numerical sensitivity inputs contain duplicates")
    if set(registered) != SUPPORTED_NUMERICAL_INPUTS:
        raise ValueError("numerical sensitivity implementation contract changed")
    rows = load_symbol_index()
    definitions: list[OfatRunDefinition] = []
    for symbol in registered:
        row = rows[symbol]
        for level in ("low", "high"):
            definitions.append(
                OfatRunDefinition(
                    run_id=f"{symbol}__{level}",
                    changed_parameter=symbol,
                    level=level,
                    value=_numeric_endpoint(row, level),
                    source_sheet=row.source_sheet,
                    source_row=row.source_row,
                )
            )
    return tuple(definitions)


def central_numerical_input_vector() -> dict[str, float]:
    rows = load_symbol_index()
    return {
        symbol: _numeric_endpoint(rows[symbol], "central")
        for symbol in load_sensitivity()["numerical_inputs"]
    }


def input_vector_for_run(definition: OfatRunDefinition) -> dict[str, float]:
    vector = central_numerical_input_vector()
    if definition.changed_parameter not in vector:
        raise ValueError(f"unregistered OFAT parameter {definition.changed_parameter}")
    vector[definition.changed_parameter] = definition.value
    return vector


def _integer_value(symbol: str, value: float) -> int:
    if not float(value).is_integer() or value < 1:
        raise ValueError(f"{symbol} sensitivity value must be a positive integer")
    return int(value)


def _lifecycle_for_run(
    base: LifecycleParameters,
    definition: OfatRunDefinition,
) -> LifecycleParameters:
    symbol = definition.changed_parameter
    value = definition.value
    updates: dict[str, Any] = {}
    if symbol == "d":
        updates["annual_degradation_rate"] = value
    elif symbol == "SL_mod":
        # Locked specification: service-life sensitivity changes evaluation T
        # without inserting an artificial module replacement.
        updates["horizon_years"] = _integer_value(symbol, value)
    elif symbol == "λ_mod":
        updates["module_failure_rate_per_year"] = value
    elif symbol == "DT_event":
        updates["downtime_hours_per_event"] = value
    elif symbol == "N_handle,asm":
        updates["assembly_handled_module_equivalents"] = value

    varied = replace(base, **updates)
    module_area = (
        base.component_disturbed_area_m2
        / base.component_handled_module_equivalents
    )
    failure_rate = (
        varied.equivalent_module_count
        * varied.module_failure_rate_per_year
    )
    varied = replace(
        varied,
        failure_rate_events_per_year=failure_rate,
        locked_expected_failure_events=failure_rate * varied.horizon_years,
        assembly_disturbed_area_m2=(
            module_area * varied.assembly_handled_module_equivalents
        ),
    )
    varied.validate_locked_derivations()
    return varied


def _cost_for_run(
    base: CostParameters,
    lifecycle: LifecycleParameters,
    definition: OfatRunDefinition,
) -> CostParameters:
    symbol = definition.changed_parameter
    value = definition.value
    updates: dict[str, Any] = {
        "horizon_years": lifecycle.horizon_years,
        "failure_rate_events_per_year": lifecycle.failure_rate_events_per_year,
    }
    field_map = {
        "m_OM": "annual_om_rate",
        "C_BIPV": "reference_bipv_cost_per_m2",
        "p_vent": "ventilated_complexity_factor",
        "p_rev": "reversibility_premium_factor",
        "r": "real_discount_rate",
        "C_rec": "recycling_service_cost_per_tonne_aud",
        "V_rec": "owner_recovery_credit_per_tonne_aud",
    }
    if symbol in field_map:
        updates[field_map[symbol]] = value
    varied = replace(base, **updates)

    direct = varied.reference_bipv_cost_per_m2
    ventilated = direct * (1.0 + varied.ventilated_complexity_factor)
    reversibility = direct * varied.reversibility_premium_factor
    eol_recycling = (
        varied.eol_pv_mass_tonnes
        * varied.recycling_service_cost_per_tonne_aud
    )
    transport = eol_recycling * varied.transport_share
    varied = replace(
        varied,
        direct_mount_cost_per_m2=direct,
        ventilated_mount_cost_per_m2=ventilated,
        reversibility_premium_per_m2=reversibility,
        cached_direct_annual_om_aud=(
            varied.bipv_area_m2 * direct * varied.annual_om_rate
        ),
        cached_ventilated_annual_om_aud=(
            varied.bipv_area_m2 * ventilated * varied.annual_om_rate
        ),
        failed_product_material_cost_per_event_aud=(
            varied.module_area_m2 * varied.reference_bipv_cost_per_m2
        ),
        eol_recycling_cost_aud=eol_recycling,
        transport_component_aud=transport,
        processing_component_aud=eol_recycling - transport,
        total_owner_recovery_credit_aud=(
            varied.eol_pv_mass_tonnes
            * varied.owner_recovery_credit_per_tonne_aud
        ),
    )
    varied.validate_locked_derivations()
    return varied


def parameters_for_run(
    definition: OfatRunDefinition,
    *,
    lifecycle_base: LifecycleParameters | None = None,
    cost_base: CostParameters | None = None,
) -> tuple[LifecycleParameters, CostParameters]:
    if definition.changed_parameter not in SUPPORTED_NUMERICAL_INPUTS:
        raise ValueError(
            f"unsupported OFAT parameter {definition.changed_parameter!r}"
        )
    if definition.level not in {"low", "high"}:
        raise ValueError(f"unsupported OFAT level {definition.level!r}")
    lifecycle_base = lifecycle_base or LifecycleParameters.from_locked_inputs()
    cost_base = cost_base or CostParameters.from_locked_inputs()
    lifecycle = _lifecycle_for_run(lifecycle_base, definition)
    cost = _cost_for_run(cost_base, lifecycle, definition)
    return lifecycle, cost


def _decision_records(
    variants: Sequence[Mapping[str, Any]],
    lifecycle_results: Sequence[Any],
    cost_results: Sequence[Any],
    evidence_results: Sequence[Any],
) -> tuple[dict[str, Any], ...]:
    records: list[dict[str, Any]] = []
    for variant, lifecycle, cost, evidence in zip(
        variants, lifecycle_results, cost_results, evidence_results
    ):
        if not (
            variant["id"]
            == lifecycle.variant_id
            == cost.variant_id
            == evidence.variant_id
        ):
            raise AssertionError("variant alignment changed in sensitivity run")
        records.append({
            **variant,
            "E_life": lifecycle.net_lifetime_energy_kwh,
            "A_life": lifecycle.lifetime_availability_ratio,
            "WLC": cost.whole_life_cost_aud,
            "B_dist": lifecycle.intervention.disturbed_area_burden_m2_event,
            "M": evidence.mechanistic,
            "I": evidence.institutional,
            "C": evidence.contextual,
            "CIRC": evidence.combined,
            "CostIntensity_aud_per_kwh": cost.cost_intensity_aud_per_kwh,
        })
    return tuple(records)


def run_numerical_ofat(
    first_year_energy_kwh: Mapping[str, float],
    *,
    variants: Sequence[Mapping[str, Any]] | None = None,
    definitions: Sequence[OfatRunDefinition] | None = None,
) -> tuple[
    tuple[Mapping[str, Any], ...],
    ParetoAnalysis,
    tuple[OfatRunResult, ...],
]:
    """Run central plus all locked low/high numerical OFAT cases."""

    variants = tuple(variants or load_variants()["variants"])
    definitions = tuple(definitions or load_ofat_run_definitions())
    lifecycle_base = LifecycleParameters.from_locked_inputs()
    cost_base = CostParameters.from_locked_inputs()
    evidence_parameters = CircularityParameters.from_locked_inputs()
    evidence = run_circularity(
        variants, parameters=evidence_parameters, gap_treatment="zero"
    )

    central_lifecycle = run_lifecycle_energy(
        variants, first_year_energy_kwh, parameters=lifecycle_base
    )
    central_cost = run_lifecycle_cost(
        variants, central_lifecycle, parameters=cost_base
    )
    central_records = _decision_records(
        variants, central_lifecycle, central_cost, evidence
    )
    central_pareto = analyze_pareto(
        central_records,
        criteria=load_primary_criteria(),
        tolerance_ulps=FLOAT_TOLERANCE_ULPS,
    )

    results: list[OfatRunResult] = []
    central_vector = central_numerical_input_vector()
    for definition in definitions:
        lifecycle_parameters, cost_parameters = parameters_for_run(
            definition,
            lifecycle_base=lifecycle_base,
            cost_base=cost_base,
        )
        lifecycle = run_lifecycle_energy(
            variants, first_year_energy_kwh, parameters=lifecycle_parameters
        )
        cost = run_lifecycle_cost(
            variants, lifecycle, parameters=cost_parameters
        )
        records = _decision_records(variants, lifecycle, cost, evidence)
        pareto = analyze_pareto(
            records,
            criteria=load_primary_criteria(),
            tolerance_ulps=FLOAT_TOLERANCE_ULPS,
        )
        input_vector = input_vector_for_run(definition)
        changed_inputs = [
            symbol for symbol in central_vector
            if input_vector[symbol] != central_vector[symbol]
        ]
        is_valid = changed_inputs == [definition.changed_parameter]
        exclusion_reason = None
        if not is_valid:
            if not changed_inputs and definition.value == central_vector[
                definition.changed_parameter
            ]:
                exclusion_reason = "locked_endpoint_equals_central"
            else:
                exclusion_reason = "ofat_input_vector_violation"
        results.append(
            OfatRunResult(
                definition=definition,
                input_vector=input_vector,
                variant_records=records,
                pareto=pareto,
                jaccard_to_central=jaccard_similarity(
                    central_pareto.non_dominated_ids,
                    pareto.non_dominated_ids,
                ),
                is_valid_sensitivity_run=is_valid,
                exclusion_reason=exclusion_reason,
            )
        )
    return central_records, central_pareto, tuple(results)


def pareto_inclusion_frequencies(
    results: Sequence[OfatRunResult],
    variant_ids: Sequence[str],
) -> dict[str, float]:
    valid_results = [result for result in results if result.is_valid_sensitivity_run]
    if not valid_results:
        raise ValueError("Pareto inclusion frequency requires valid OFAT runs")
    denominator = len(valid_results)
    return {
        variant_id: sum(
            variant_id in result.pareto.non_dominated_ids
            for result in valid_results
        ) / denominator
        for variant_id in variant_ids
    }


IMPLEMENTATION_STATUS = "IMPLEMENTED_NUMERICAL_OFAT_GATE"
