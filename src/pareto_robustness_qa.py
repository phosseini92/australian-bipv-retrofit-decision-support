"""Hard-fail checks for locked Pareto criterion/GAP structural robustness."""

from __future__ import annotations

from dataclasses import asdict
import math
from typing import Any, Mapping, Sequence

from .config_loader import load_model, load_sensitivity
from .energy_qa import QaResult
from .pareto import StructuralParetoScenario


def evaluate_pareto_robustness_assertions(
    central_records: Sequence[Mapping[str, Any]],
    gap_excluded_records: Sequence[Mapping[str, Any]],
    scenarios: Sequence[StructuralParetoScenario],
) -> list[QaResult]:
    if len(central_records) != 8 or len(gap_excluded_records) != 8:
        raise AssertionError("Pareto robustness requires V01–V08 in both evidence treatments")
    qa: list[QaResult] = []

    expected_ids = (
        "primary_gap_zero",
        "combined_gap_zero",
        "primary_gap_excluded",
        "combined_gap_excluded",
    )
    structural_ids = {
        item["id"] for item in load_sensitivity()["structural_runs"]
    }
    rb01_ok = (
        tuple(item.scenario_id for item in scenarios) == expected_ids
        and "combined_circularity_criterion" in structural_ids
        and "exclude_gap_from_denominator" in structural_ids
    )
    qa.append(QaResult(
        "RB01", "PASS" if rb01_ok else "FAIL",
        "The full primary/combined × GAP-zero/excluded structural matrix is present and maps to the locked named runs.",
    ))

    expected_primary = ("E_life", "A_life", "WLC", "B_dist", "M", "I", "C")
    expected_combined = ("E_life", "A_life", "WLC", "B_dist", "CIRC")
    rb02_ok = all(
        tuple(item.field for item in scenario.analysis.criteria)
        == (expected_primary if scenario.criterion_structure == "three_dimensions" else expected_combined)
        for scenario in scenarios
    )
    qa.append(QaResult(
        "RB02", "PASS" if rb02_ok else "FAIL",
        "Combined runs replace exactly M/I/C with CIRC; no other decision criterion changes.",
    ))

    evidence_math_ok = all(
        math.isclose(
            float(record["CIRC"]),
            (float(record["M"]) + float(record["I"]) + float(record["C"])) / 3.0,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        for records in (central_records, gap_excluded_records)
        for record in records
    )
    non_evidence_fields = ("E_life", "A_life", "WLC", "B_dist")
    gap_isolated_ok = all(
        all(float(a[field]) == float(b[field]) for field in non_evidence_fields)
        for a, b in zip(central_records, gap_excluded_records)
    )
    rb03_ok = evidence_math_ok and gap_isolated_ok
    qa.append(QaResult(
        "RB03", "PASS" if rb03_ok else "FAIL",
        "CIRC is recomputed as the unweighted M/I/C mean and GAP treatment changes evidence dimensions only.",
    ))

    expected_set = ("V02", "V04", "V06", "V08")
    expected_edges = {
        ("V02", "V01"), ("V02", "V03"), ("V04", "V03"),
        ("V06", "V05"), ("V06", "V07"), ("V08", "V07"),
    }
    rb04_ok = all(
        scenario.analysis.non_dominated_ids == expected_set
        and math.isclose(scenario.jaccard_to_central_primary, 1.0)
        and {
            (pair.dominator, pair.dominated)
            for pair in scenario.analysis.dominance_pairs
        } == expected_edges
        for scenario in scenarios
    )
    qa.append(QaResult(
        "RB04", "PASS" if rb04_ok else "FAIL",
        "All four structural scenarios retain the same six dominance edges and V02/V04/V06/V08 non-dominated set; Jaccard=1.0.",
    ))

    pareto_config = load_model()["pareto"]
    q12_ok = (
        pareto_config["weights"] is None
        and pareto_config["normalization"] is None
        and all(
            all(item.direction in {"maximize", "minimize"} for item in scenario.analysis.criteria)
            for scenario in scenarios
        )
    )
    qa.append(QaResult(
        "Q12", "PASS" if q12_ok else "FAIL",
        "Every robustness run uses raw directed criteria with no weights and no normalization.",
    ))

    q14_ok = all(
        math.isfinite(float(record[field]))
        for records in (central_records, gap_excluded_records)
        for record in records
        for field in ("E_life", "A_life", "WLC", "B_dist", "M", "I", "C", "CIRC")
    ) and all(
        math.isfinite(scenario.jaccard_to_central_primary)
        for scenario in scenarios
    )
    qa.append(QaResult(
        "Q14", "PASS" if q14_ok else "FAIL",
        "All structural-run criteria and set-comparison metrics are finite.",
    ))

    failed = [item.id for item in qa if item.status != "PASS"]
    if failed:
        raise AssertionError(f"Pareto robustness QA failed: {failed}")
    return qa


def pareto_robustness_qa_as_dicts(
    results: Sequence[QaResult],
) -> list[dict[str, Any]]:
    return [asdict(item) for item in results]


IMPLEMENTATION_STATUS = "IMPLEMENTED_PARETO_ROBUSTNESS_GATE"
