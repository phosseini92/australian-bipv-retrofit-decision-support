"""Hard-fail internal and locked QA checks for the lifecycle-cost gate."""

from __future__ import annotations

from dataclasses import asdict
import math
from typing import Any, Sequence

from .energy_qa import QaResult
from .lifecycle_cost import CostParameters, LifecycleCostResult


def _close(a: float, b: float, tolerance: float) -> bool:
    return math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)


def evaluate_cost_assertions(
    results: Sequence[LifecycleCostResult],
    parameters: CostParameters,
    *,
    tolerance: float = 1e-10,
) -> list[QaResult]:
    """Evaluate cost reconciliations plus formal Q08–Q10 and Q14."""

    if len(results) != 8:
        raise AssertionError("cost QA requires exactly V01–V08")
    qa: list[QaResult] = []

    c01_ok = True
    for item in results:
        expected_mount_rate = (
            parameters.direct_mount_cost_per_m2
            if item.mounting == "direct"
            else parameters.ventilated_mount_cost_per_m2
        )
        expected_mount = parameters.bipv_area_m2 * expected_mount_rate
        expected_rev = (
            parameters.bipv_area_m2
            * parameters.reversibility_premium_per_m2
            if item.connection == "reversible_mechanical"
            else 0.0
        )
        c01_ok &= _close(item.mounting_initial_cost_aud, expected_mount, tolerance)
        c01_ok &= _close(item.reversibility_premium_aud, expected_rev, tolerance)
        c01_ok &= _close(
            item.initial_cost_aud,
            expected_mount + expected_rev,
            tolerance,
        )
        c01_ok &= _close(
            item.annual_om_cost_aud,
            parameters.annual_om_rate * item.initial_cost_aud,
            tolerance,
        )
        c01_ok &= _close(
            item.replacement.annual_expected_material_cost_aud,
            parameters.failure_rate_events_per_year
            * parameters.failed_product_material_cost_per_event_aud,
            tolerance,
        )
    qa.append(
        QaResult(
            "C01",
            "PASS" if c01_ok else "FAIL",
            (
                "Mounting cost, reversibility premium, C0, annual O&M, and "
                "expected corrective material cost reproduce the locked "
                "equations."
            ),
        )
    )

    c02_ok = True
    for item in results:
        discounted_schedule = sum(
            year.discounted_total_aud for year in item.annual
        )
        component_sum = (
            item.pv_om_aud
            + item.pv_corrective_material_aud
            + item.pv_access_aud
            + item.pv_inverter_aud
            + item.pv_eol_net_aud
        )
        c02_ok &= _close(
            item.whole_life_cost_aud,
            item.initial_cost_aud + discounted_schedule,
            tolerance,
        )
        c02_ok &= _close(discounted_schedule, component_sum, tolerance)
        c02_ok &= _close(
            item.cost_intensity_aud_per_kwh,
            item.whole_life_cost_aud / item.lifetime_energy_kwh,
            tolerance,
        )
    qa.append(
        QaResult(
            "C02",
            "PASS" if c02_ok else "FAIL",
            (
                "The annual discounted cash-flow schedule reconciles to the "
                "component PV totals, WLC, and WLC/E_life."
            ),
        )
    )

    c03_ok = all(
        item.replacement.access_cost_per_event_aud == 0.0
        and item.pv_access_aud == 0.0
        and item.eol_removal_cost_aud == 0.0
        for item in results
    )
    qa.append(
        QaResult(
            "C03",
            "PASS" if c03_ok else "FAIL",
            (
                "Unsupported access and EoL-removal tariffs are excluded from "
                "the central accounting and remain break-even variables."
            ),
        )
    )

    c04_ok = True
    for mounting in ("direct", "ventilated"):
        for connection in ("low_reversibility", "reversible_mechanical"):
            group = [
                item
                for item in results
                if item.mounting == mounting and item.connection == connection
            ]
            c04_ok &= len(group) == 2
            c04_ok &= _close(
                group[0].whole_life_cost_aud,
                group[1].whole_life_cost_aud,
                tolerance,
            )
    qa.append(
        QaResult(
            "C04",
            "PASS" if c04_ok else "FAIL",
            (
                "Replacement scope does not create an unsupported central "
                "cost difference; its energy and disturbance effects remain "
                "separate."
            ),
        )
    )

    inverter_costs = {
        round(item.inverter_reference_cost_per_event_aud, 12)
        for item in results
    }
    inverter_schedules = {item.inverter_replacement_years for item in results}
    inverter_pvs = {round(item.pv_inverter_aud, 12) for item in results}
    q08_ok = (
        len(inverter_costs) == 1
        and len(inverter_schedules) == 1
        and len(inverter_pvs) == 1
    )
    qa.append(
        QaResult(
            "Q08",
            "PASS" if q08_ok else "FAIL",
            (
                "The reference inverter allowance, replacement schedule, and "
                "discounted inverter cost are common across V01–V08."
            ),
        )
    )

    material_event_costs = {
        round(item.replacement.event_material_cost_aud, 12)
        for item in results
    }
    material_annual_costs = {
        round(item.replacement.annual_expected_material_cost_aud, 12)
        for item in results
    }
    q09_ok = (
        parameters.assembly_extra_material_cost_per_event_aud == 0.0
        and len(material_event_costs) == 1
        and len(material_annual_costs) == 1
        and all(
            item.replacement.assembly_extra_material_cost_per_event_aud == 0.0
            for item in results
        )
    )
    qa.append(
        QaResult(
            "Q09",
            "PASS" if q09_ok else "FAIL",
            (
                "Corrective material cost represents one failed product per "
                "event; adjacent assembly-level products add no discarded "
                "material cost."
            ),
        )
    )

    q10_ok = (
        parameters.total_owner_recovery_credit_aud == 0.0
        and parameters.owner_recovery_credit_per_tonne_aud == 0.0
        and parameters.separate_transport_rule == "Not added in baseline"
        and _close(
            parameters.transport_component_aud
            + parameters.processing_component_aud,
            parameters.eol_recycling_cost_aud,
            tolerance,
        )
        and all(
            item.owner_recovery_credit_aud == 0.0
            and _close(
                item.eol_net_cost_aud,
                item.eol_recycling_cost_aud + item.eol_removal_cost_aud,
                tolerance,
            )
            for item in results
        )
    )
    qa.append(
        QaResult(
            "Q10",
            "PASS" if q10_ok else "FAIL",
            (
                "Central owner recovery is zero and the transport component "
                "is a decomposition of the all-in recycling fee, not an "
                "additional charge."
            ),
        )
    )

    scalar_keys = (
        "C_mount_initial_aud",
        "C_rev_aud",
        "C0_aud",
        "C_OM_annual_aud",
        "C_rep_event_aud",
        "C_corr_material_annual_aud",
        "C_extra_assembly_event_aud",
        "C_access_event_aud",
        "C_access_annual_aud",
        "C_inv_ref_event_aud",
        "C_EOL_recycling_aud",
        "C_EOL_removal_aud",
        "V_owner_aud",
        "C_EOL_net_aud",
        "PV_OM_aud",
        "PV_corrective_material_aud",
        "PV_access_aud",
        "PV_inverter_aud",
        "PV_EOL_net_aud",
        "WLC_aud",
        "E_life_kwh",
        "CostIntensity_aud_per_kwh",
    )
    q14_ok = True
    for item in results:
        record = item.as_record()
        q14_ok &= all(
            math.isfinite(float(record[key])) and float(record[key]) >= 0.0
            for key in scalar_keys
        )
        q14_ok &= all(
            math.isfinite(year.nominal_total_aud)
            and math.isfinite(year.discounted_total_aud)
            and year.nominal_total_aud >= 0.0
            and year.discounted_total_aud >= 0.0
            for year in item.annual
        )
    qa.append(
        QaResult(
            "Q14",
            "PASS" if q14_ok else "FAIL",
            "All central lifecycle-cost metrics are finite and non-negative.",
        )
    )

    failed = [item.id for item in qa if item.status != "PASS"]
    if failed:
        raise AssertionError(f"lifecycle-cost QA failed: {failed}")
    return qa


def cost_qa_as_dicts(results: Sequence[QaResult]) -> list[dict[str, Any]]:
    return [asdict(item) for item in results]


IMPLEMENTATION_STATUS = "IMPLEMENTED_INTEGRATION_GATE"
