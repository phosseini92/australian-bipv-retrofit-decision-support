"""Hard-fail QA for locked energy structural sensitivity cases."""

from __future__ import annotations

from dataclasses import asdict
import math
from typing import Any, Sequence

from .energy_qa import QaResult
from .input_loader import load_symbol_index
from .structural_sensitivity import EnergyStructuralScenario


def evaluate_energy_structural_assertions(
    scenarios: Sequence[EnergyStructuralScenario],
) -> list[QaResult]:
    qa: list[QaResult] = []
    by_id = {item.scenario_id: item for item in scenarios}
    rows = load_symbol_index()

    es01_ok = tuple(item.scenario_id for item in scenarios) == (
        "central", "west_orientation", "equal_temperature_control"
    ) and len(by_id) == 3
    qa.append(QaResult(
        "ES01", "PASS" if es01_ok else "FAIL",
        "Central plus the two registered energy structural cases execute once in controlled order.",
    ))

    es02_ok = (
        by_id["central"].surface_azimuth == float(rows["γ_N"].central)
        and by_id["west_orientation"].surface_azimuth
        == float(rows["γ_W"].central)
        and by_id["equal_temperature_control"].surface_azimuth
        == float(rows["γ_N"].central)
        and by_id["west_orientation"].input_symbol == "ORI"
        and by_id["equal_temperature_control"].input_symbol == "Tcase"
    )
    qa.append(QaResult(
        "ES02", "PASS" if es02_ok else "FAIL",
        "Orientation and temperature controls use only the locked north/west azimuths and registered structural labels.",
    ))

    equal = by_id["equal_temperature_control"].first_year_energy_kwh
    es03_ok = math.isclose(
        equal["direct"], equal["ventilated"], rel_tol=0.0, abs_tol=0.0
    )
    qa.append(QaResult(
        "ES03", "PASS" if es03_ok else "FAIL",
        "The equal-temperature control assigns the same hourly-temperature energy result to direct and ventilated variants.",
    ))

    es04_ok = (
        by_id["central"].pareto.non_dominated_ids
        == ("V02", "V04", "V06", "V08")
        and by_id["west_orientation"].pareto.non_dominated_ids
        == ("V02", "V04", "V06", "V08")
        and by_id["west_orientation"].jaccard_to_central == 1.0
    )
    qa.append(QaResult(
        "ES04", "PASS" if es04_ok else "FAIL",
        "West orientation retains the central non-dominated set and Jaccard similarity 1.0.",
    ))

    es05_ok = (
        by_id["equal_temperature_control"].pareto.non_dominated_ids
        == ("V02", "V04")
        and by_id["equal_temperature_control"].jaccard_to_central == 0.5
    )
    qa.append(QaResult(
        "ES05", "PASS" if es05_ok else "FAIL",
        "Removing the mounting-temperature energy difference yields V02/V04 and Jaccard 0.5; this structural dependence is reported, not hidden.",
    ))

    finite_ok = all(
        math.isfinite(float(value))
        for scenario in scenarios
        for value in scenario.first_year_energy_kwh.values()
    ) and all(
        math.isfinite(float(record[field]))
        for scenario in scenarios
        for record in scenario.variant_records
        for field in (
            "E1_thermal", "E_life", "A_life", "WLC",
            "CostIntensity_aud_per_kwh", "B_dist", "M", "I", "C", "CIRC",
        )
    )
    qa.append(QaResult(
        "Q14", "PASS" if finite_ok else "FAIL",
        "All 24 structural-scenario variant rows and energy/stability metrics are finite.",
    ))

    failed = [item.id for item in qa if item.status != "PASS"]
    if failed:
        raise AssertionError(f"Energy structural sensitivity QA failed: {failed}")
    return qa


def energy_structural_qa_as_dicts(
    results: Sequence[QaResult],
) -> list[dict[str, Any]]:
    return [asdict(item) for item in results]


IMPLEMENTATION_STATUS = "IMPLEMENTED_ENERGY_STRUCTURAL_GATE"
