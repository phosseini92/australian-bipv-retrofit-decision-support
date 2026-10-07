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


IMPLEMENTATION_STATUS = "IMPLEMENTED_PRIMARY_PARETO_GATE"
