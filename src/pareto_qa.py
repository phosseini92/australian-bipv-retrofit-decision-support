"""Hard-fail dominance checks for the central primary Pareto Gate."""

from __future__ import annotations

from dataclasses import asdict
import math
from typing import Any, Mapping, Sequence

from .energy_qa import QaResult
from .pareto import ParetoAnalysis, load_primary_criteria


def evaluate_pareto_assertions(
    records: Sequence[Mapping[str, Any]],
    analysis: ParetoAnalysis,
) -> list[QaResult]:
    if len(records) != 8:
        raise AssertionError("Pareto Gate requires exactly V01–V08")
    qa: list[QaResult] = []

    expected_ids = tuple(f"V{i:02d}" for i in range(1, 9))
    d01_ok = tuple(str(row["id"]) for row in records) == expected_ids
    qa.append(QaResult(
        "D01", "PASS" if d01_ok else "FAIL",
        "The central decision table contains V01–V08 exactly once in locked order.",
    ))

    pair_keys = {(pair.dominator, pair.dominated) for pair in analysis.dominance_pairs}
    d02_ok = (
        all(a != b for a, b in pair_keys)
        and all((b, a) not in pair_keys for a, b in pair_keys)
        and all(
            outcome.is_non_dominated == (len(outcome.dominated_by) == 0)
            for outcome in analysis.outcomes
        )
    )
    qa.append(QaResult(
        "D02", "PASS" if d02_ok else "FAIL",
        "Dominance is irreflexive and asymmetric; non-dominated flags equal zero incoming dominance edges.",
    ))

    expected_pairs = {
        ("V02", "V01"), ("V02", "V03"), ("V04", "V03"),
        ("V06", "V05"), ("V06", "V07"), ("V08", "V07"),
    }
    d03_ok = pair_keys == expected_pairs
    qa.append(QaResult(
        "D03", "PASS" if d03_ok else "FAIL",
        "The six central dominance edges reproduce the locked factor logic without extra advantages.",
    ))

    expected_set = ("V02", "V04", "V06", "V08")
    d04_ok = analysis.non_dominated_ids == expected_set
    qa.append(QaResult(
        "D04", "PASS" if d04_ok else "FAIL",
        "The central primary non-dominated set is V02, V04, V06, and V08.",
    ))

    configured = load_primary_criteria()
    q12_ok = analysis.criteria == configured and [
        (item.field, item.direction) for item in configured
    ] == [
        ("E_life", "maximize"), ("A_life", "maximize"),
        ("WLC", "minimize"), ("B_dist", "minimize"),
        ("M", "maximize"), ("I", "maximize"), ("C", "maximize"),
    ]
    qa.append(QaResult(
        "Q12", "PASS" if q12_ok else "FAIL",
        "Dominance uses the seven locked raw criteria and directions with no weights or normalization.",
    ))

    q14_ok = all(
        math.isfinite(float(row[field]))
        for row in records
        for field in ("E_life", "A_life", "WLC", "B_dist", "M", "I", "C")
    )
    qa.append(QaResult(
        "Q14", "PASS" if q14_ok else "FAIL",
        "All raw central Pareto criteria are finite.",
    ))

    failed = [item.id for item in qa if item.status != "PASS"]
    if failed:
        raise AssertionError(f"Pareto Gate QA failed: {failed}")
    return qa


def pareto_qa_as_dicts(results: Sequence[QaResult]) -> list[dict[str, Any]]:
    return [asdict(item) for item in results]


IMPLEMENTATION_STATUS = "IMPLEMENTED_PRIMARY_PARETO_GATE"
