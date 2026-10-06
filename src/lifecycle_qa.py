"""Hard-fail lifecycle-energy checks from the locked Q01–Q14 contract."""

from __future__ import annotations

from dataclasses import asdict
import math
from typing import Any, Sequence

from .energy_qa import QaResult
from .lifecycle_energy import LifecycleEnergyResult, LifecycleParameters


def _close(a: float, b: float, tolerance: float) -> bool:
    return math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)


def evaluate_lifecycle_assertions(
    results: Sequence[LifecycleEnergyResult],
    parameters: LifecycleParameters,
    *,
    tolerance: float = 1e-10,
) -> list[QaResult]:
    """Evaluate Q04, Q06–Q09, and Q14 for the lifecycle-energy gate."""

    if len(results) != 8:
        raise AssertionError("lifecycle QA requires exactly V01–V08")
    qa: list[QaResult] = []

    q04_ok = True
    for mounting in ("direct", "ventilated"):
        group = [item for item in results if item.mounting == mounting]
        q04_ok &= len(group) == 4
        q04_ok &= all(
            _close(item.first_year_energy_kwh, group[0].first_year_energy_kwh, tolerance)
            for item in group
        )
        q04_ok &= all(
            _close(
                item.gross_lifetime_energy_kwh,
                group[0].gross_lifetime_energy_kwh,
                tolerance,
            )
            for item in group
        )
        for scope in ("assembly_level", "component_level"):
            scoped = [item for item in group if item.replacement_scope == scope]
            q04_ok &= len(scoped) == 2
            q04_ok &= _close(
                scoped[0].net_lifetime_energy_kwh,
                scoped[1].net_lifetime_energy_kwh,
                tolerance,
            )
    qa.append(
        QaResult(
            "Q04",
            "PASS" if q04_ok else "FAIL",
            (
                "Replacement scope leaves E1 and pre-availability lifetime "
                "energy unchanged; only disturbed-area availability changes "
                "net lifetime energy."
            ),
        )
    )

    q06_ok = all(
        _close(item.annual[0].degradation_factor, 1.0, tolerance)
        and _close(
            item.annual[0].energy_degraded_kwh,
            item.first_year_energy_kwh,
            tolerance,
        )
        and all(
            _close(
                year.energy_net_kwh,
                year.energy_degraded_kwh * year.availability_factor,
                tolerance,
            )
            for year in item.annual
        )
        for item in results
    )
    qa.append(
        QaResult(
            "Q06",
            "PASS" if q06_ok else "FAIL",
            (
                "Year 1 starts at the already loss-adjusted E1 without another "
                "LID deduction; availability is applied afterward as a "
                "separate factor."
            ),
        )
    )

    q07_ok = all(
        all(
            _close(
                year.degradation_factor,
                max(
                    0.0,
                    1.0
                    - parameters.annual_degradation_rate * (year.year - 1),
                ),
                tolerance,
            )
            for year in item.annual
        )
        for item in results
    )
    qa.append(
        QaResult(
            "Q07",
            "PASS" if q07_ok else "FAIL",
            "Every annual factor matches max(0, 1 - d*(y-1)); no compound recursion is used.",
        )
    )

    schedules = {item.inverter_replacement_years for item in results}
    expected_schedule = (15,) if parameters.horizon_years == 30 else None
    q08_ok = len(schedules) == 1 and (
        expected_schedule is None or next(iter(schedules)) == expected_schedule
    )
    qa.append(
        QaResult(
            "Q08",
            "PASS" if q08_ok else "FAIL",
            (
                "The scheduled inverter replacement years are identical "
                "across all variants; central T=30 gives year 15 only."
            ),
        )
    )

    replacement_counts = {
        round(item.intervention.expected_replaced_module_equivalents, 12)
        for item in results
    }
    replacement_masses = {
        round(item.intervention.material_replacement_mass_kg, 12)
        for item in results
    }
    assembly = {
        (item.mounting, item.connection): item
        for item in results
        if item.replacement_scope == "assembly_level"
    }
    component = {
        (item.mounting, item.connection): item
        for item in results
        if item.replacement_scope == "component_level"
    }
    q09_ok = (
        _close(
            parameters.replaced_module_equivalents_per_event,
            1.0,
            tolerance,
        )
        and len(replacement_counts) == 1
        and len(replacement_masses) == 1
        and assembly.keys() == component.keys()
        and all(
            assembly[key].intervention.handled_scope_burden_module_event
            > component[key].intervention.handled_scope_burden_module_event
            for key in assembly
        )
    )
    qa.append(
        QaResult(
            "Q09",
            "PASS" if q09_ok else "FAIL",
            (
                "Assembly variants increase temporary handling/disturbance "
                "only; expected replaced units and material mass remain one "
                "failed product per event."
            ),
        )
    )

    scalar_keys = (
        "E1_thermal_kwh",
        "E_life_gross_kwh",
        "E_life_kwh",
        "A_life",
        "A_annual",
        "q_disturbed",
        "N_fail_expected",
        "B_dist_m2_event",
        "B_handle_module_event",
        "N_replace_expected",
        "M_replace_kg",
    )
    q14_ok = True
    for item in results:
        record = item.as_record()
        q14_ok &= all(
            math.isfinite(float(record[key])) and float(record[key]) >= 0.0
            for key in scalar_keys
        )
        q14_ok &= all(
            math.isfinite(year.energy_degraded_kwh)
            and math.isfinite(year.energy_net_kwh)
            and year.energy_degraded_kwh >= 0.0
            and year.energy_net_kwh >= 0.0
            for year in item.annual
        )
    qa.append(
        QaResult(
            "Q14",
            "PASS" if q14_ok else "FAIL",
            (
                "All lifecycle-energy, availability, intervention, and mass "
                "metrics are finite and non-negative."
            ),
        )
    )

    failed = [item.id for item in qa if item.status != "PASS"]
    if failed:
        raise AssertionError(f"lifecycle-energy QA failed: {failed}")
    return qa


def lifecycle_qa_as_dicts(results: Sequence[QaResult]) -> list[dict[str, Any]]:
    return [asdict(item) for item in results]


IMPLEMENTATION_STATUS = "IMPLEMENTED_INTEGRATION_GATE"
