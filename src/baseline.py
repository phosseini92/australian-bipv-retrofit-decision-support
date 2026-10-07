"""Formal baseline orchestration after all locked implementation gates pass."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .break_even import (
    BreakEvenAnalysis,
    CONNECTION_PAIRS,
    MOUNTING_PAIRS,
    REPLACEMENT_SCOPE_PAIRS,
    run_break_even_analysis,
)
from .break_even_qa import evaluate_break_even_assertions
from .circularity import CircularityParameters, run_circularity
from .config_loader import load_variants
from .cost_qa import evaluate_cost_assertions
from .energy_qa import build_variant_energy_records, evaluate_q01_to_q05
from .evidence_qa import evaluate_evidence_assertions
from .input_loader import load_symbol_index
from .lifecycle_cost import CostParameters, run_lifecycle_cost
from .lifecycle_energy import LifecycleParameters, run_lifecycle_energy
from .lifecycle_qa import evaluate_lifecycle_assertions
from .pareto import (
    FLOAT_TOLERANCE_ULPS,
    ParetoAnalysis,
    StructuralParetoScenario,
    analyze_pareto,
    analyze_structural_robustness,
    load_primary_criteria,
)
from .pareto_qa import evaluate_pareto_assertions
from .pareto_robustness_qa import evaluate_pareto_robustness_assertions
from .pv_energy import EnergyParameters, run_year_one_energy
from .sensitivity import OfatRunResult, run_numerical_ofat
from .sensitivity_qa import evaluate_sensitivity_assertions
from .structural_sensitivity import EnergyStructuralScenario, run_energy_structural_sensitivity
from .structural_sensitivity_qa import evaluate_energy_structural_assertions
from .weather import WeatherDataset


CONTRAST_METRICS = (
    "E1_thermal", "E_life", "A_life", "WLC",
    "CostIntensity_aud_per_kwh", "B_dist", "M", "I", "C", "CIRC",
)


@dataclass(frozen=True)
class BaselineAnalysis:
    central_records: tuple[Mapping[str, Any], ...]
    gap_excluded_records: tuple[Mapping[str, Any], ...]
    primary_pareto: ParetoAnalysis
    circularity_robustness: tuple[StructuralParetoScenario, ...]
    numerical_ofat: tuple[OfatRunResult, ...]
    energy_structural: tuple[EnergyStructuralScenario, ...]
    break_even: BreakEvenAnalysis
    factor_contrasts: tuple[Mapping[str, Any], ...]
    qa_by_gate: Mapping[str, tuple[Mapping[str, str], ...]]


def _qa_records(results: list[Any]) -> tuple[Mapping[str, str], ...]:
    return tuple(
        {"id": item.id, "status": item.status, "evidence": item.evidence}
        for item in results
    )


def _factor_contrasts(
    records: tuple[Mapping[str, Any], ...],
) -> tuple[Mapping[str, Any], ...]:
    by_id = {str(record["id"]): record for record in records}
    definitions = (
        ("mounting", "ventilated_minus_direct", MOUNTING_PAIRS),
        ("connection", "reversible_minus_low", CONNECTION_PAIRS),
        ("replacement_scope", "component_minus_assembly", REPLACEMENT_SCOPE_PAIRS),
    )
    contrasts: list[dict[str, Any]] = []
    for factor, direction, pairs in definitions:
        for comparison_id, variant_a, variant_b in pairs:
            a = by_id[variant_a]
            b = by_id[variant_b]
            contrasts.append({
                "factor": factor,
                "contrast_direction": direction,
                "comparison_id": comparison_id,
                "variant_a": variant_a,
                "variant_b": variant_b,
                **{
                    f"delta_{metric}": float(a[metric]) - float(b[metric])
                    for metric in CONTRAST_METRICS
                },
            })
    return tuple(contrasts)


def run_formal_baseline(weather: WeatherDataset) -> BaselineAnalysis:
    """Execute all locked central, sensitivity, Pareto, and break-even paths."""

    variants = tuple(load_variants()["variants"])
    rows = load_symbol_index()
    energy_parameters = EnergyParameters.from_locked_inputs()
    lifecycle_parameters = LifecycleParameters.from_locked_inputs()
    cost_parameters = CostParameters.from_locked_inputs()
    circularity_parameters = CircularityParameters.from_locked_inputs()

    energy_results = {
        mounting: run_year_one_energy(
            weather,
            mounting=mounting,
            surface_azimuth=float(rows["γ_N"].central),
            parameters=energy_parameters,
        )
        for mounting in ("direct", "ventilated")
    }
    first_year_energy = {
        mounting: result.energy_kwh
        for mounting, result in energy_results.items()
    }
    energy_records = build_variant_energy_records(
        variants,
        energy_results,
        {
            "A_BIPV_m2": float(rows["A_BIPV"].central),
            "PVtech": str(rows["PVtech"].central),
            "Pdc0_kWp": energy_parameters.pdc0_kwp,
            "INV": str(rows["INV"].central),
            "Pac0_kW": energy_parameters.pac0_kw,
        },
    )
    energy_qa = evaluate_q01_to_q05(
        energy_records, energy_results, pac0_kw=energy_parameters.pac0_kw
    )
    lifecycle = run_lifecycle_energy(
        variants, first_year_energy, parameters=lifecycle_parameters
    )
    lifecycle_qa = evaluate_lifecycle_assertions(lifecycle, lifecycle_parameters)
    costs = run_lifecycle_cost(variants, lifecycle, parameters=cost_parameters)
    cost_qa = evaluate_cost_assertions(costs, cost_parameters)
    evidence = run_circularity(
        variants, parameters=circularity_parameters, gap_treatment="zero"
    )
    gap_excluded = run_circularity(
        variants, parameters=circularity_parameters, gap_treatment="exclude"
    )
    evidence_qa = evaluate_evidence_assertions(
        evidence, gap_excluded, circularity_parameters
    )

    central_records: list[dict[str, Any]] = []
    gap_records: list[dict[str, Any]] = []
    for variant, life, cost, central_ev, gap_ev in zip(
        variants, lifecycle, costs, evidence, gap_excluded
    ):
        if not (
            variant["id"] == life.variant_id == cost.variant_id
            == central_ev.variant_id == gap_ev.variant_id
        ):
            raise AssertionError("variant alignment changed in formal baseline")
        common = {
            **variant,
            "E1_thermal": life.first_year_energy_kwh,
            "E_life": life.net_lifetime_energy_kwh,
            "A_life": life.lifetime_availability_ratio,
            "WLC": cost.whole_life_cost_aud,
            "CostIntensity_aud_per_kwh": cost.cost_intensity_aud_per_kwh,
            "B_dist": life.intervention.disturbed_area_burden_m2_event,
        }
        central_records.append({
            **common, "M": central_ev.mechanistic, "I": central_ev.institutional,
            "C": central_ev.contextual, "CIRC": central_ev.combined,
        })
        gap_records.append({
            **common, "M": gap_ev.mechanistic, "I": gap_ev.institutional,
            "C": gap_ev.contextual, "CIRC": gap_ev.combined,
        })
    central = tuple(central_records)
    gap = tuple(gap_records)
    primary = analyze_pareto(
        central, criteria=load_primary_criteria(), tolerance_ulps=FLOAT_TOLERANCE_ULPS
    )
    pareto_qa = evaluate_pareto_assertions(central, primary)
    structural_pareto = analyze_structural_robustness(central, gap)
    robustness_qa = evaluate_pareto_robustness_assertions(
        central, gap, structural_pareto
    )
    sensitivity_central, sensitivity_pareto, numerical_ofat = run_numerical_ofat(
        first_year_energy, variants=variants
    )
    sensitivity_fields = tuple(sensitivity_central[0])
    if tuple(
        {field: record[field] for field in sensitivity_fields}
        for record in central
    ) != tuple(sensitivity_central):
        raise AssertionError("OFAT central decision metrics differ from baseline")
    if sensitivity_pareto.non_dominated_ids != primary.non_dominated_ids:
        raise AssertionError("OFAT central Pareto set differs from baseline")
    sensitivity_qa = evaluate_sensitivity_assertions(
        sensitivity_central, numerical_ofat
    )
    energy_structural = run_energy_structural_sensitivity(weather, variants=variants)
    energy_structural_qa = evaluate_energy_structural_assertions(energy_structural)
    break_even = run_break_even_analysis(first_year_energy, variants=variants)
    break_even_qa = evaluate_break_even_assertions(break_even)

    qa_by_gate = {
        "energy": _qa_records(energy_qa),
        "lifecycle_energy": _qa_records(lifecycle_qa),
        "lifecycle_cost": _qa_records(cost_qa),
        "evidence": _qa_records(evidence_qa),
        "pareto_primary": _qa_records(pareto_qa),
        "pareto_robustness": _qa_records(robustness_qa),
        "numerical_ofat": _qa_records(sensitivity_qa),
        "energy_structural": _qa_records(energy_structural_qa),
        "break_even": _qa_records(break_even_qa),
    }
    if any(
        item["status"] != "PASS"
        for results in qa_by_gate.values()
        for item in results
    ):
        raise AssertionError("formal baseline cannot export with failed QA")

    return BaselineAnalysis(
        central_records=central,
        gap_excluded_records=gap,
        primary_pareto=primary,
        circularity_robustness=structural_pareto,
        numerical_ofat=numerical_ofat,
        energy_structural=energy_structural,
        break_even=break_even,
        factor_contrasts=_factor_contrasts(central),
        qa_by_gate=qa_by_gate,
    )


IMPLEMENTATION_STATUS = "FORMAL_BASELINE_IMPLEMENTED_CC002"
