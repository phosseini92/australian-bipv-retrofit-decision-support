"""Hard-fail checks for the PSCF-informed Evidence Gate."""

from __future__ import annotations

from dataclasses import asdict
import math
from typing import Any, Sequence

from .circularity import CircularityParameters, CircularityResult
from .energy_qa import QaResult


def _close(a: float, b: float, tolerance: float) -> bool:
    return math.isclose(a, b, rel_tol=tolerance, abs_tol=tolerance)


def evaluate_evidence_assertions(
    central: Sequence[CircularityResult],
    gap_excluded: Sequence[CircularityResult],
    parameters: CircularityParameters,
    *, tolerance: float = 1e-12,
) -> list[QaResult]:
    if len(central) != 8 or len(gap_excluded) != 8:
        raise AssertionError("Evidence Gate requires exactly V01–V08 in both runs")
    qa: list[QaResult] = []

    e01_ok = (
        parameters.pscf_method_rule == "No native quantitative score"
        and all(item.gap_treatment == "zero" for item in central)
        and all(item.gap_treatment == "exclude" for item in gap_excluded)
    )
    qa.append(QaResult(
        "E01", "PASS" if e01_ok else "FAIL",
        "The published PSCF remains qualitative; outputs are labelled as the study-specific evidence-readiness construct.",
    ))

    expected_central = {
        ("low_reversibility", "assembly_level"): (0.25, 0.48333333333333334),
        ("low_reversibility", "component_level"): (0.5, 0.5666666666666667),
        ("reversible_mechanical", "assembly_level"): (0.5, 0.5666666666666667),
        ("reversible_mechanical", "component_level"): (0.75, 0.65),
    }
    e02_ok = all(
        _close(item.mechanistic, expected_central[(item.connection, item.replacement_scope)][0], tolerance)
        and _close(item.institutional, 0.7, tolerance)
        and _close(item.contextual, 0.5, tolerance)
        and _close(item.combined, expected_central[(item.connection, item.replacement_scope)][1], tolerance)
        for item in central
    )
    qa.append(QaResult(
        "E02", "PASS" if e02_ok else "FAIL",
        "Item-level arithmetic reproduces all locked central M, I, C, and combined cached values.",
    ))

    gap_expected = {
        ("low_reversibility", "assembly_level"): (1 / 3, 0.5694444444444444),
        ("low_reversibility", "component_level"): (2 / 3, 0.6805555555555555),
        ("reversible_mechanical", "assembly_level"): (2 / 3, 0.6805555555555555),
        ("reversible_mechanical", "component_level"): (1.0, 0.7916666666666666),
    }
    e03_ok = all(
        _close(item.mechanistic, gap_expected[(item.connection, item.replacement_scope)][0], tolerance)
        and _close(item.institutional, 0.875, tolerance)
        and _close(item.contextual, 0.5, tolerance)
        and _close(item.combined, gap_expected[(item.connection, item.replacement_scope)][1], tolerance)
        and {e.symbol for e in item.items if e.is_gap} == {"M_DFD_DOC", "I_TAKE"}
        and next(e for e in item.items if e.symbol == "C_LOG").evidence_state == "CONSTRAINT"
        for item in gap_excluded
    )
    qa.append(QaResult(
        "E03", "PASS" if e03_ok else "FAIL",
        "Structural robustness excludes only M_DFD_DOC and I_TAKE GAP items; the explicit C_LOG constraint remains zero in its denominator.",
    ))

    q11_ok = (
        len({round(item.institutional, 12) for item in central}) == 1
        and len({round(item.contextual, 12) for item in central}) == 1
        and len({round(item.institutional, 12) for item in gap_excluded}) == 1
        and len({round(item.contextual, 12) for item in gap_excluded}) == 1
    )
    qa.append(QaResult(
        "Q11", "PASS" if q11_ok else "FAIL",
        "Institutional and contextual evidence values remain identical across V01–V08 in both gap treatments.",
    ))

    e04_ok = True
    for results in (central, gap_excluded):
        by_design: dict[tuple[str, str], list[CircularityResult]] = {}
        for item in results:
            by_design.setdefault((item.connection, item.replacement_scope), []).append(item)
        e04_ok &= all(
            len(group) == 2
            and len({(x.mechanistic, x.institutional, x.contextual, x.combined) for x in group}) == 1
            for group in by_design.values()
        )
    qa.append(QaResult(
        "E04", "PASS" if e04_ok else "FAIL",
        "Direct versus ventilated mounting creates no evidence-readiness difference.",
    ))

    q14_ok = all(
        math.isfinite(value) and 0.0 <= value <= 1.0
        for results in (central, gap_excluded)
        for item in results
        for value in (item.mechanistic, item.institutional, item.contextual, item.combined)
    )
    qa.append(QaResult(
        "Q14", "PASS" if q14_ok else "FAIL",
        "All exported evidence-readiness dimensions are finite and bounded in [0, 1].",
    ))

    failed = [item.id for item in qa if item.status != "PASS"]
    if failed:
        raise AssertionError(f"Evidence Gate QA failed: {failed}")
    return qa


def evidence_qa_as_dicts(results: Sequence[QaResult]) -> list[dict[str, Any]]:
    return [asdict(item) for item in results]


IMPLEMENTATION_STATUS = "IMPLEMENTED_EVIDENCE_GATE"
