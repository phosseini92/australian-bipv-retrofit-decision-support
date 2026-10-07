"""Raw-criterion Pareto dominance; no weights and no normalization."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

from .config_loader import load_model


ALLOWED_DIRECTIONS = {"maximize", "minimize"}
FLOAT_TOLERANCE_ULPS = 8


@dataclass(frozen=True)
class Criterion:
    field: str
    direction: str


@dataclass(frozen=True)
class DominancePair:
    dominator: str
    dominated: str
    strictly_better: tuple[str, ...]
    equivalent_within_float_tolerance: tuple[str, ...]

    def as_record(self) -> dict[str, Any]:
        return {
            "dominator": self.dominator,
            "dominated": self.dominated,
            "strictly_better_criteria": list(self.strictly_better),
            "equivalent_criteria": list(self.equivalent_within_float_tolerance),
        }


@dataclass(frozen=True)
class ParetoOutcome:
    variant_id: str
    is_non_dominated: bool
    dominated_by: tuple[str, ...]
    dominates: tuple[str, ...]

    def as_record(self) -> dict[str, Any]:
        return {
            "id": self.variant_id,
            "is_non_dominated": self.is_non_dominated,
            "dominated_by": list(self.dominated_by),
            "dominates": list(self.dominates),
        }


@dataclass(frozen=True)
class ParetoAnalysis:
    criteria: tuple[Criterion, ...]
    outcomes: tuple[ParetoOutcome, ...]
    dominance_pairs: tuple[DominancePair, ...]

    @property
    def non_dominated_ids(self) -> tuple[str, ...]:
        return tuple(
            item.variant_id for item in self.outcomes if item.is_non_dominated
        )


@dataclass(frozen=True)
class StructuralParetoScenario:
    scenario_id: str
    criterion_structure: str
    gap_treatment: str
    analysis: ParetoAnalysis
    jaccard_to_central_primary: float

    def as_record(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "criterion_structure": self.criterion_structure,
            "gap_treatment": self.gap_treatment,
            "criteria": [
                {"field": item.field, "direction": item.direction}
                for item in self.analysis.criteria
            ],
            "non_dominated_set": list(self.analysis.non_dominated_ids),
            "dominance_pairs": [
                item.as_record() for item in self.analysis.dominance_pairs
            ],
            "jaccard_to_central_primary": self.jaccard_to_central_primary,
        }


def load_primary_criteria() -> tuple[Criterion, ...]:
    """Load and validate the locked raw primary criterion vector."""

    pareto = load_model()["pareto"]
    if pareto["weights"] is not None:
        raise ValueError("Pareto weights must remain null")
    if pareto["normalization"] is not None:
        raise ValueError("Pareto normalization must remain null")
    if pareto["tolerance_use"] != "floating_point_noise_only":
        raise ValueError("Pareto tolerance rule changed")
    criteria = tuple(
        Criterion(str(item["field"]), str(item["direction"]))
        for item in pareto["primary_criteria"]
    )
    if not criteria or len({item.field for item in criteria}) != len(criteria):
        raise ValueError("Pareto criteria must be non-empty and unique")
    invalid = [item.direction for item in criteria if item.direction not in ALLOWED_DIRECTIONS]
    if invalid:
        raise ValueError(f"invalid Pareto direction(s): {invalid}")
    return criteria


def load_combined_circularity_criteria() -> tuple[Criterion, ...]:
    """Replace the locked M/I/C criteria with the locked combined CIRC field."""

    model = load_model()["pareto"]
    contract = model["criterion_structure_test"]
    if contract["replace"] != ["M", "I", "C"]:
        raise ValueError("combined-circularity replacement contract changed")
    if contract["with"] != {"field": "CIRC", "direction": "maximize"}:
        raise ValueError("combined-circularity criterion contract changed")
    primary = load_primary_criteria()
    retained = tuple(item for item in primary if item.field not in contract["replace"])
    expected_retained = ("E_life", "A_life", "WLC", "B_dist")
    if tuple(item.field for item in retained) != expected_retained:
        raise ValueError("primary criterion structure changed")
    return retained + (
        Criterion(
            str(contract["with"]["field"]),
            str(contract["with"]["direction"]),
        ),
    )


def _finite_value(record: Mapping[str, Any], field: str) -> float:
    if field not in record:
        raise KeyError(f"missing Pareto criterion {field}")
    value = float(record[field])
    if not math.isfinite(value):
        raise ValueError(f"Pareto criterion {field} must be finite")
    return value


def _float_tolerance(a: float, b: float, ulps: int) -> float:
    if isinstance(ulps, bool) or not isinstance(ulps, int) or ulps < 0:
        raise ValueError("tolerance_ulps must be a non-negative integer")
    return ulps * max(math.ulp(a), math.ulp(b))


def dominance_detail(
    a: Mapping[str, Any],
    b: Mapping[str, Any],
    criteria: Sequence[Criterion],
    *,
    tolerance_ulps: int = FLOAT_TOLERANCE_ULPS,
) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    """Return dominance plus strict/equivalent criterion labels.

    Tolerance is bounded to a small number of machine ULPs and therefore only
    suppresses floating-point noise; it does not establish a practical
    equivalence band.
    """

    no_worse = True
    strictly_better: list[str] = []
    equivalent: list[str] = []
    for criterion in criteria:
        av = _finite_value(a, criterion.field)
        bv = _finite_value(b, criterion.field)
        tolerance = _float_tolerance(av, bv, tolerance_ulps)
        if criterion.direction == "maximize":
            no_worse &= av >= bv - tolerance
            if av > bv + tolerance:
                strictly_better.append(criterion.field)
            elif abs(av - bv) <= tolerance:
                equivalent.append(criterion.field)
        elif criterion.direction == "minimize":
            no_worse &= av <= bv + tolerance
            if av < bv - tolerance:
                strictly_better.append(criterion.field)
            elif abs(av - bv) <= tolerance:
                equivalent.append(criterion.field)
        else:
            raise ValueError(f"invalid Pareto direction: {criterion.direction}")
    return no_worse and bool(strictly_better), tuple(strictly_better), tuple(equivalent)


def dominates(
    a: Mapping[str, Any],
    b: Mapping[str, Any],
    criteria: Sequence[Criterion],
    *,
    tolerance_ulps: int = FLOAT_TOLERANCE_ULPS,
) -> bool:
    return dominance_detail(
        a, b, criteria, tolerance_ulps=tolerance_ulps
    )[0]


def analyze_pareto(
    records: Sequence[Mapping[str, Any]],
    *,
    criteria: Sequence[Criterion] | None = None,
    tolerance_ulps: int = FLOAT_TOLERANCE_ULPS,
) -> ParetoAnalysis:
    """Evaluate ordered raw-criterion dominance for the supplied variants."""

    criteria = tuple(criteria or load_primary_criteria())
    if not records:
        raise ValueError("Pareto analysis requires at least one record")
    ids = [str(record["id"]) for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Pareto record IDs must be unique")
    for record in records:
        for criterion in criteria:
            _finite_value(record, criterion.field)

    pairs: list[DominancePair] = []
    for i, a in enumerate(records):
        for j, b in enumerate(records):
            if i == j:
                continue
            is_dominant, strict, equivalent = dominance_detail(
                a, b, criteria, tolerance_ulps=tolerance_ulps
            )
            if is_dominant:
                pairs.append(
                    DominancePair(ids[i], ids[j], strict, equivalent)
                )

    outcomes = tuple(
        ParetoOutcome(
            variant_id=variant_id,
            is_non_dominated=not any(
                pair.dominated == variant_id for pair in pairs
            ),
            dominated_by=tuple(
                pair.dominator for pair in pairs if pair.dominated == variant_id
            ),
            dominates=tuple(
                pair.dominated for pair in pairs if pair.dominator == variant_id
            ),
        )
        for variant_id in ids
    )
    return ParetoAnalysis(criteria, outcomes, tuple(pairs))


def jaccard_similarity(
    reference_ids: Sequence[str], candidate_ids: Sequence[str]
) -> float:
    """Return set Jaccard similarity; this is a robustness summary, not probability."""

    reference = set(reference_ids)
    candidate = set(candidate_ids)
    union = reference | candidate
    return 1.0 if not union else len(reference & candidate) / len(union)


def analyze_structural_robustness(
    central_records: Sequence[Mapping[str, Any]],
    gap_excluded_records: Sequence[Mapping[str, Any]],
    *,
    tolerance_ulps: int = FLOAT_TOLERANCE_ULPS,
) -> tuple[StructuralParetoScenario, ...]:
    """Run the locked 2×2 criterion-structure × GAP-treatment matrix."""

    central_ids = tuple(str(record["id"]) for record in central_records)
    gap_ids = tuple(str(record["id"]) for record in gap_excluded_records)
    if central_ids != gap_ids:
        raise ValueError("central and GAP-excluded variant order differs")
    invariant_fields = (
        "short_code", "mounting", "connection", "replacement_scope",
        "E_life", "A_life", "WLC", "B_dist",
    )
    for central, gap_excluded in zip(central_records, gap_excluded_records):
        changed = [
            field for field in invariant_fields
            if central[field] != gap_excluded[field]
        ]
        if changed:
            raise ValueError(
                f"GAP treatment changed non-evidence fields for {central['id']}: {changed}"
            )

    primary = load_primary_criteria()
    combined = load_combined_circularity_criteria()
    definitions = (
        ("primary_gap_zero", "three_dimensions", "zero", central_records, primary),
        ("combined_gap_zero", "combined_CIRC", "zero", central_records, combined),
        (
            "primary_gap_excluded", "three_dimensions", "exclude",
            gap_excluded_records, primary,
        ),
        (
            "combined_gap_excluded", "combined_CIRC", "exclude",
            gap_excluded_records, combined,
        ),
    )
    analyses = [
        analyze_pareto(records, criteria=criteria, tolerance_ulps=tolerance_ulps)
        for _, _, _, records, criteria in definitions
    ]
    reference_set = analyses[0].non_dominated_ids
    return tuple(
        StructuralParetoScenario(
            scenario_id=scenario_id,
            criterion_structure=structure,
            gap_treatment=gap_treatment,
            analysis=analysis,
            jaccard_to_central_primary=jaccard_similarity(
                reference_set, analysis.non_dominated_ids
            ),
        )
        for (scenario_id, structure, gap_treatment, _, _), analysis in zip(
            definitions, analyses
        )
    )


IMPLEMENTATION_STATUS = "IMPLEMENTED_PARETO_ROBUSTNESS_GATE"
