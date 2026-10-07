"""Hard-fail checks for computed break-even outputs and explicit blockers."""

from __future__ import annotations

from dataclasses import asdict
import math
from typing import Any, Sequence

from .break_even import (
    BreakEvenAnalysis,
    CONNECTION_PAIRS,
    MOUNTING_PAIRS,
    REPLACEMENT_SCOPE_PAIRS,
)
from .energy_qa import QaResult


def evaluate_break_even_assertions(
    analysis: BreakEvenAnalysis,
) -> list[QaResult]:
    qa: list[QaResult] = []

    pair_ok = (
        len(analysis.maximum_premium) == len(CONNECTION_PAIRS) == 4
        and len(analysis.required_access_saving_locked_formula) == 4
        and len(analysis.required_access_saving_wlc_diagnostic) == 4
        and len(analysis.service_life) == len(MOUNTING_PAIRS) == 4
        and len(analysis.recovery_value) == 4
        and len(analysis.discount_rate_candidate_matrix)
        == len(CONNECTION_PAIRS + MOUNTING_PAIRS + REPLACEMENT_SCOPE_PAIRS)
    )
    qa.append(QaResult(
        "BE01", "PASS" if pair_ok else "FAIL",
        "All locked matched connection and mounting comparisons execute; the diagnostic discount matrix covers every one-factor pair without choosing a preferred pair.",
    ))

    premium_ok = all(
        item.output_id == "BE_rev"
        and item.status == "ZERO_THRESHOLD"
        and item.value == 0.0
        for item in analysis.maximum_premium
    )
    qa.append(QaResult(
        "BE02", "PASS" if premium_ok else "FAIL",
        "The explicit maximum-premium equation returns zero under the central scenario because no downstream monetary saving is asserted.",
    ))

    locked_access = analysis.required_access_saving_locked_formula
    wlc_access = analysis.required_access_saving_wlc_diagnostic
    access_ok = all(
        locked.value is not None
        and diagnostic.value is not None
        and locked.value > 0.0
        and diagnostic.value > locked.value
        and locked.residual is not None
        and locked.residual > 0.0
        and diagnostic.residual is not None
        and math.isclose(diagnostic.residual, 0.0, abs_tol=1e-8)
        for locked, diagnostic in zip(locked_access, wlc_access)
    )
    qa.append(QaResult(
        "BE03", "PASS" if access_ok else "FAIL",
        "Both the explicit Section 11.2 access threshold and the full-WLC reconciliation diagnostic are preserved; their non-zero difference exposes the locked formula mismatch.",
    ))

    life_ok = all(
        item.output_id == "BE_life"
        and item.status == "NO_BREAK_EVEN_LE_50_YEARS"
        and item.value is None
        and item.lower_bound == 10.0
        and item.upper_bound == 50.0
        for item in analysis.service_life
    )
    qa.append(QaResult(
        "BE04", "PASS" if life_ok else "FAIL",
        "Every matched mounting contrast searches integer T=10–50 with locked inverter intervals and explicitly reports no root when parity is not reached.",
    ))

    recovery_ok = all(
        item.output_id == "BE_rec"
        and item.status == "ROOT_FOUND"
        and item.value is not None
        and item.value > 0.0
        and item.residual is not None
        and math.isclose(item.residual, 0.0, abs_tol=1e-8)
        for item in analysis.recovery_value
    )
    qa.append(QaResult(
        "BE05", "PASS" if recovery_ok else "FAIL",
        "Incremental owner-recovery thresholds reproduce WLC equality for all matched connection pairs and remain explicitly scenario-qualified.",
    ))

    rate_statuses = [
        item.status for item in analysis.discount_rate_candidate_matrix
    ]
    rate_ok = (
        analysis.discount_rate_primary.status
        == "LOCKED_PAIRWISE_COMPARISON_NOT_SPECIFIED"
        and rate_statuses.count("NO_SIGN_CHANGE_WITHIN_BOUND") == 8
        and rate_statuses.count("IDENTICALLY_EQUAL_WITHIN_TOLERANCE") == 4
    )
    qa.append(QaResult(
        "BE06", "PASS" if rate_ok else "FAIL",
        "The missing locked BE_r pair is not invented. Candidate one-factor contrasts explicitly report eight no-sign-change cases and four all-rate ties over 0–15%.",
    ))

    mismatches_ok = (
        [item["id"] for item in analysis.locked_spec_mismatches]
        == ["BE-M01", "BE-M02", "BE-M03"]
        and [item["status"] for item in analysis.locked_spec_mismatches]
        == ["MISMATCH", "BLOCKER", "MISMATCH"]
    )
    qa.append(QaResult(
        "BE07", "PASS" if mismatches_ok else "FAIL",
        "The access-formula/WLC inconsistency, absent selected discount-rate pair, and cross-document intervention-frequency omission are explicit; none is silently resolved in code.",
    ))

    finite_ok = True
    for item in analysis.all_numeric_results():
        for value in (
            item.value, item.lower_bound, item.upper_bound, item.residual
        ):
            if value is not None:
                finite_ok &= math.isfinite(float(value))
        if item.value is None:
            finite_ok &= item.status in {
                "NO_BREAK_EVEN_LE_50_YEARS",
                "NO_SIGN_CHANGE_WITHIN_BOUND",
                "IDENTICALLY_EQUAL_WITHIN_TOLERANCE",
            }
    finite_ok &= analysis.discount_rate_primary.value is None
    finite_ok &= bool(analysis.discount_rate_primary.status)
    qa.append(QaResult(
        "Q14", "PASS" if finite_ok else "FAIL",
        "All numeric break-even outputs are finite; absent and non-unique roots use explicit status strings and null values rather than NaN/Inf.",
    ))

    failed = [item.id for item in qa if item.status != "PASS"]
    if failed:
        raise AssertionError(f"Break-even QA failed: {failed}")
    return qa


def break_even_qa_as_dicts(
    results: Sequence[QaResult],
) -> list[dict[str, Any]]:
    return [asdict(item) for item in results]


IMPLEMENTATION_STATUS = "IMPLEMENTED_BLOCKED_BY_LOCKED_SPEC_CLARIFICATION"
