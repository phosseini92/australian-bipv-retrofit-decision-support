"""Locked orientation and equal-temperature structural sensitivity runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .circularity import CircularityParameters, run_circularity
from .config_loader import load_sensitivity, load_variants
from .input_loader import load_symbol_index
from .lifecycle_cost import CostParameters, run_lifecycle_cost
from .lifecycle_energy import LifecycleParameters, run_lifecycle_energy
from .pareto import (
    FLOAT_TOLERANCE_ULPS,
    ParetoAnalysis,
    analyze_pareto,
    jaccard_similarity,
    load_primary_criteria,
)
from .pv_energy import EnergyParameters, YearOneEnergyResult, run_year_one_energy
from .weather import WeatherDataset


ENERGY_STRUCTURAL_IDS = ("west_orientation", "equal_temperature_control")


@dataclass(frozen=True)
class EnergyStructuralScenario:
    scenario_id: str
    input_symbol: str
    setting: str
    surface_azimuth: float
    first_year_energy_kwh: Mapping[str, float]
    variant_records: tuple[Mapping[str, Any], ...]
    pareto: ParetoAnalysis
    jaccard_to_central: float

    def as_record(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "input_symbol": self.input_symbol,
            "setting": self.setting,
            "surface_azimuth": self.surface_azimuth,
            "first_year_energy_kwh": dict(self.first_year_energy_kwh),
            "non_dominated_set": list(self.pareto.non_dominated_ids),
            "dominance_pairs": [
                item.as_record() for item in self.pareto.dominance_pairs
            ],
            "jaccard_to_central": self.jaccard_to_central,
            "variant_records": list(self.variant_records),
        }


def _decision_records(
    variants: Sequence[Mapping[str, Any]],
    first_year_energy: Mapping[str, float],
) -> tuple[dict[str, Any], ...]:
    lifecycle = run_lifecycle_energy(
        variants,
        first_year_energy,
        parameters=LifecycleParameters.from_locked_inputs(),
    )
    costs = run_lifecycle_cost(
        variants,
        lifecycle,
        parameters=CostParameters.from_locked_inputs(),
    )
    evidence = run_circularity(
        variants,
        parameters=CircularityParameters.from_locked_inputs(),
        gap_treatment="zero",
    )
    records: list[dict[str, Any]] = []
    for variant, life, cost, circularity in zip(
        variants, lifecycle, costs, evidence
    ):
        if not (
            variant["id"]
            == life.variant_id
            == cost.variant_id
            == circularity.variant_id
        ):
            raise AssertionError("variant alignment changed in structural run")
        records.append({
            **variant,
            "E1_thermal": first_year_energy[str(variant["mounting"])],
            "E_life": life.net_lifetime_energy_kwh,
            "A_life": life.lifetime_availability_ratio,
            "WLC": cost.whole_life_cost_aud,
            "CostIntensity_aud_per_kwh": cost.cost_intensity_aud_per_kwh,
            "B_dist": life.intervention.disturbed_area_burden_m2_event,
            "M": circularity.mechanistic,
            "I": circularity.institutional,
            "C": circularity.contextual,
            "CIRC": circularity.combined,
        })
    return tuple(records)


def _energy_values(
    results: Mapping[str, YearOneEnergyResult],
) -> dict[str, float]:
    return {key: float(value.energy_kwh) for key, value in results.items()}


def run_energy_structural_sensitivity(
    weather: WeatherDataset,
    *,
    variants: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[EnergyStructuralScenario, ...]:
    """Run central, west-orientation, and equal-temperature full pipelines."""

    variants = tuple(variants or load_variants()["variants"])
    registered = {
        item["id"]: item for item in load_sensitivity()["structural_runs"]
    }
    if not all(item in registered for item in ENERGY_STRUCTURAL_IDS):
        raise ValueError("locked energy structural-run registry changed")
    rows = load_symbol_index()
    parameters = EnergyParameters.from_locked_inputs()
    north = float(rows["γ_N"].central)
    west = float(rows["γ_W"].central)

    central_energy = _energy_values({
        mounting: run_year_one_energy(
            weather,
            mounting=mounting,
            surface_azimuth=north,
            parameters=parameters,
        )
        for mounting in ("direct", "ventilated")
    })
    west_energy = _energy_values({
        mounting: run_year_one_energy(
            weather,
            mounting=mounting,
            surface_azimuth=west,
            parameters=parameters,
        )
        for mounting in ("direct", "ventilated")
    })
    equal_result = run_year_one_energy(
        weather,
        mounting="equal_temperature_control",
        surface_azimuth=north,
        parameters=parameters,
    )
    equal_energy = {
        "direct": float(equal_result.energy_kwh),
        "ventilated": float(equal_result.energy_kwh),
    }
    definitions = (
        ("central", "CENTRAL", "North; mounting-specific SAPM", north, central_energy),
        (
            "west_orientation",
            str(registered["west_orientation"]["input"]),
            str(registered["west_orientation"]["setting"]),
            west,
            west_energy,
        ),
        (
            "equal_temperature_control",
            str(registered["equal_temperature_control"]["input"]),
            str(registered["equal_temperature_control"]["setting"]),
            north,
            equal_energy,
        ),
    )
    prepared: list[tuple[Any, ...]] = []
    for scenario_id, input_symbol, setting, azimuth, energy in definitions:
        records = _decision_records(variants, energy)
        pareto = analyze_pareto(
            records,
            criteria=load_primary_criteria(),
            tolerance_ulps=FLOAT_TOLERANCE_ULPS,
        )
        prepared.append(
            (scenario_id, input_symbol, setting, azimuth, energy, records, pareto)
        )
    central_set = prepared[0][-1].non_dominated_ids
    return tuple(
        EnergyStructuralScenario(
            scenario_id=scenario_id,
            input_symbol=input_symbol,
            setting=setting,
            surface_azimuth=azimuth,
            first_year_energy_kwh=energy,
            variant_records=records,
            pareto=pareto,
            jaccard_to_central=jaccard_similarity(
                central_set, pareto.non_dominated_ids
            ),
        )
        for (
            scenario_id,
            input_symbol,
            setting,
            azimuth,
            energy,
            records,
            pareto,
        ) in prepared
    )


IMPLEMENTATION_STATUS = "IMPLEMENTED_ENERGY_STRUCTURAL_GATE"
