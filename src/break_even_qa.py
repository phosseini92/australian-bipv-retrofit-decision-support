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
        and len(analysis.required_access_saving_primary_wlc) == 4
        and len(analysis.required_access_saving_initial_premium_diagnostic) == 4
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

    primary_access = analysis.required_access_saving_primary_wlc
    diagnostic_access = (
        analysis.required_access_saving_initial_premium_diagnostic
    )
    access_ok = all(
        primary.value is not None
        and diagnostic.value is not None
        and primary.value > diagnostic.value > 0.0
        and primary.residual is not None
        and math.isclose(primary.residual, 0.0, abs_tol=1e-8)
        and diagnostic.residual is not None
        and diagnostic.residual > 0.0
        and primary.scenario
        == "cc002_d1_b_primary_full_discounted_wlc_equality"
        for primary, diagnostic in zip(primary_access, diagnostic_access)
    )
    qa.append(QaResult(
        "BE03", "PASS" if access_ok else "FAIL",
        "CC-002 D1-B is enforced: full-WLC equality is primary and the lower initial-premium-only Section 11.2 value remains a labelled diagnostic.",
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

    rate_statuses = [item.status for item in analysis.discount_rate_candidate_matrix]
    rate_ok = (
        len(analysis.discount_rate_primary) == 4
        and tuple(item.comparison_id for item in analysis.discount_rate_primary)
        == tuple(item[0] for item in CONNECTION_PAIRS)
        and all(
            item.status == "NO_SIGN_CHANGE_WITHIN_BOUND"
            and item.value is None
            and item.scenario
            == "cc002_d2_a_all_matched_reversible_vs_low_pairs"
            for item in analysis.discount_rate_primary
        )
        and rate_statuses.count("NO_SIGN_CHANGE_WITHIN_BOUND") == 8
        and rate_statuses.count("IDENTICALLY_EQUAL_WITHIN_TOLERANCE") == 4
    )
    qa.append(QaResult(
        "BE06", "PASS" if rate_ok else "FAIL",
        "CC-002 D2-A is enforced: all four matched reversible/low pairs are primary BE_r comparisons and each explicitly has no root over 0–15%; no pair is privileged.",
    ))

    approval_ok = (
        [item["decision"] for item in analysis.cc002_approval]
        == ["D1-B", "D2-A", "D3-A"]
        and all(
            item["status"] == "APPROVED_IMPLEMENTED"
            for item in analysis.cc002_approval
        )
        and not analysis.open_locked_spec_issues
    )
    qa.append(QaResult(
        "BE07", "PASS" if approval_ok else "FAIL",
        "CC-002 approval D1-B + D2-A + D3-A is recorded and implemented with no remaining locked-source Break-even issue.",
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
    finite_ok &= all(
        item.value is None and bool(item.status)
        for item in analysis.discount_rate_primary
    )
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


IMPLEMENTATION_STATUS = "IMPLEMENTED_BREAK_EVEN_GATE_PASSED"
