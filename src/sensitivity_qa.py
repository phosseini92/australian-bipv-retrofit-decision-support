"""Hard-fail checks for the locked numerical OFAT Sensitivity Gate."""

from __future__ import annotations

from dataclasses import asdict
import math
from typing import Any, Mapping, Sequence

from .config_loader import load_sensitivity
from .energy_qa import QaResult
from .sensitivity import (
    OfatRunResult,
    central_numerical_input_vector,
    pareto_inclusion_frequencies,
)


def evaluate_sensitivity_assertions(
    central_records: Sequence[Mapping[str, Any]],
    results: Sequence[OfatRunResult],
) -> list[QaResult]:
    qa: list[QaResult] = []
    contract = load_sensitivity()
    symbols = tuple(contract["numerical_inputs"])

    expected_run_ids = tuple(
        f"{symbol}__{level}"
        for symbol in symbols
        for level in ("low", "high")
    )
    s01_ok = (
        contract["execution_rule"] == "OFAT"
        and len(results) == 24
        and tuple(item.definition.run_id for item in results) == expected_run_ids
        and sum(item.is_valid_sensitivity_run for item in results) == 23
    )
    qa.append(QaResult(
        "S01", "PASS" if s01_ok else "FAIL",
        "All 24 registered endpoints execute in parameter order; 23 are valid changed-input OFAT runs and V_rec low is the transparent central-value duplicate.",
    ))

    central_vector = central_numerical_input_vector()
    q13_ok = True
    for result in results:
        changed = [
            symbol for symbol in symbols
            if result.input_vector[symbol] != central_vector[symbol]
        ]
        if result.is_valid_sensitivity_run:
            q13_ok &= changed == [result.definition.changed_parameter]
            q13_ok &= result.exclusion_reason is None
        else:
            q13_ok &= result.definition.run_id == "V_rec__low"
            q13_ok &= changed == []
            q13_ok &= result.exclusion_reason == "locked_endpoint_equals_central"
        q13_ok &= result.definition.changed_parameter in symbols
        q13_ok &= result.definition.level in {"low", "high"}
    qa.append(QaResult(
        "Q13", "PASS" if q13_ok else "FAIL",
        "Every valid sensitivity run differs from central in exactly one input. V_rec low equals central zero, is flagged, and is excluded from valid-run stability denominators.",
    ))

    required_manifest = set(contract["required_run_manifest_fields"])
    available_manifest = {
        "changed_parameter", "source_row", "value", "variant_set",
        "code_version", "timestamp",
    }
    s02_ok = required_manifest <= available_manifest and all(
        result.definition.source_sheet
        and result.definition.source_row > 0
        and len(result.variant_records) == 8
        for result in results
    )
    qa.append(QaResult(
        "S02", "PASS" if s02_ok else "FAIL",
        "Every run can emit all locked manifest fields, source provenance, and the complete V01–V08 result set.",
    ))

    variant_ids = tuple(str(row["id"]) for row in central_records)
    valid_results = [result for result in results if result.is_valid_sensitivity_run]
    frequencies = pareto_inclusion_frequencies(results, variant_ids)
    s03_ok = all(
        math.isclose(
            frequencies[variant_id],
            sum(
                variant_id in result.pareto.non_dominated_ids
                for result in valid_results
            ) / len(valid_results),
            rel_tol=0.0,
            abs_tol=0.0,
        )
        for variant_id in variant_ids
    )
    qa.append(QaResult(
        "S03", "PASS" if s03_ok else "FAIL",
        "Pareto inclusion frequencies equal non-dominated counts divided by the 23 valid changed-input OFAT runs.",
    ))

    s04_ok = all(
        0.0 <= result.jaccard_to_central <= 1.0
        and bool(result.pareto.non_dominated_ids)
        for result in valid_results
    )
    qa.append(QaResult(
        "S04", "PASS" if s04_ok else "FAIL",
        "Every valid run has a non-empty Pareto set and bounded Jaccard similarity to the central set.",
    ))

    scalar_fields = (
        "E_life", "A_life", "WLC", "B_dist", "M", "I", "C", "CIRC",
        "CostIntensity_aud_per_kwh",
    )
    q14_ok = all(
        math.isfinite(float(record[field]))
        for result in results
        for record in result.variant_records
        for field in scalar_fields
    ) and all(
        math.isfinite(result.jaccard_to_central) for result in results
    )
    qa.append(QaResult(
        "Q14", "PASS" if q14_ok else "FAIL",
        "All 192 variant-run metric rows and all stability summaries are finite.",
    ))

    s05_ok = not any(
        result.definition.changed_parameter
        in {item["input"] for item in contract["structural_runs"]}
        for result in results
    )
    qa.append(QaResult(
        "S05", "PASS" if s05_ok else "FAIL",
        "No structural run, break-even variable, or unregistered evidence case is mixed into numerical OFAT.",
    ))

    failed = [item.id for item in qa if item.status != "PASS"]
    if failed:
        raise AssertionError(f"Numerical OFAT QA failed: {failed}")
    return qa


def sensitivity_qa_as_dicts(results: Sequence[QaResult]) -> list[dict[str, Any]]:
    return [asdict(item) for item in results]


IMPLEMENTATION_STATUS = "IMPLEMENTED_NUMERICAL_OFAT_GATE"
