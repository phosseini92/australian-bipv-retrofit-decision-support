"""PSCF-informed, item-level evidence-readiness calculations.

The published PSCF remains qualitative. The 0/0.5/1 values implemented here
are the study-specific evidence-readiness coding layer locked by the controlled
input table; they are not represented as a native PSCF score.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

from .input_loader import InputRow, load_symbol_index


DIMENSION_ITEMS = {
    "M": ("M_REV", "M_REP", "M_MAINT", "M_DFD_DOC"),
    "I": ("I_DOC", "I_TRACE", "I_WARR", "I_TAKE", "I_STEW"),
    "C": ("C_REC", "C_PROC", "C_REUSE", "C_LOG"),
}
EVIDENCE_STATES = {
    "M_REV": "DESIGN_ATTRIBUTE",
    "M_REP": "DESIGN_ATTRIBUTE",
    "M_MAINT": "ENABLING",
    "M_DFD_DOC": "GAP",
    "I_DOC": "ENABLING",
    "I_TRACE": "ENABLING",
    "I_WARR": "ENABLING",
    "I_TAKE": "GAP",
    "I_STEW": "PARTIAL_EMERGING",
    "C_REC": "ENABLING",
    "C_PROC": "PARTIAL_EMERGING",
    "C_REUSE": "PARTIAL_EMERGING",
    "C_LOG": "CONSTRAINT",
}
CENTRAL_ITEM_VALUES = {
    "M_MAINT": 1.0,
    "M_DFD_DOC": 0.0,
    "I_DOC": 1.0,
    "I_TRACE": 1.0,
    "I_WARR": 1.0,
    "I_TAKE": 0.0,
    "I_STEW": 0.5,
    "C_REC": 1.0,
    "C_PROC": 0.5,
    "C_REUSE": 0.5,
    "C_LOG": 0.0,
}
CACHED_PROFILES = {
    ("low_reversibility", "assembly_level"): ("M_LA", "CIRC_LA"),
    ("low_reversibility", "component_level"): ("M_LC", "CIRC_LC"),
    ("reversible_mechanical", "assembly_level"): ("M_RA", "CIRC_RA"),
    ("reversible_mechanical", "component_level"): ("M_RC", "CIRC_RC"),
}


def _numeric(row: InputRow) -> float:
    if not hasattr(row.central, "as_tuple"):
        raise TypeError(f"locked evidence input {row.symbol} is not numeric")
    value = float(row.central)
    if not math.isfinite(value):
        raise ValueError(f"locked evidence input {row.symbol} is not finite")
    return value


@dataclass(frozen=True)
class EvidenceItem:
    symbol: str
    dimension: str
    value: float
    evidence_state: str
    is_gap: bool
    status: str
    source_id: str
    source_sheet: str
    source_row: int

    def as_record(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "dimension": self.dimension,
            "value": self.value,
            "evidence_state": self.evidence_state,
            "is_gap": self.is_gap,
            "input_status": self.status,
            "source_id": self.source_id,
            "source_sheet": self.source_sheet,
            "source_row": self.source_row,
        }


@dataclass(frozen=True)
class CircularityParameters:
    pscf_method_rule: str
    evidence_code_rule: str
    missing_evidence_rule: str
    rows: Mapping[str, InputRow]

    @classmethod
    def from_locked_inputs(cls) -> "CircularityParameters":
        rows = load_symbol_index()
        parameters = cls(
            pscf_method_rule=str(rows["PSCF"].central),
            evidence_code_rule=str(rows["E_code"].central),
            missing_evidence_rule=str(rows["E_gap"].central),
            rows=rows,
        )
        parameters.validate_locked_contract()
        return parameters

    def validate_locked_contract(self, *, tolerance: float = 1e-12) -> None:
        if self.pscf_method_rule != "No native quantitative score":
            raise ValueError("published PSCF method rule changed")
        if self.evidence_code_rule != (
            "0 = constrained/gap; 0.5 = partial/emerging; "
            "1 = explicit enabling evidence"
        ):
            raise ValueError("study-specific evidence coding rule changed")
        if self.missing_evidence_rule != "No public evidence → 0 and flag GAP":
            raise ValueError("missing-evidence rule changed")

        for symbol, expected in CENTRAL_ITEM_VALUES.items():
            if not math.isclose(
                _numeric(self.rows[symbol]), expected, rel_tol=tolerance, abs_tol=tolerance
            ):
                raise ValueError(f"locked evidence item {symbol} changed")

        if self.rows["M_DFD_DOC"].status != "LOCKED" or "GAP" not in self.rows[
            "M_DFD_DOC"
        ].notes:
            raise ValueError("M_DFD_DOC must remain a documented GAP")
        if self.rows["I_TAKE"].status != "LOCKED" or "GAP" not in self.rows[
            "I_TAKE"
        ].notes:
            raise ValueError("I_TAKE must remain a documented GAP")
        if "CONSTRAINT" not in self.rows["C_LOG"].notes:
            raise ValueError("C_LOG must remain an explicit constraint")

        for connection, scope in CACHED_PROFILES:
            items = self.build_items(connection, scope)
            dimensions = _dimension_means(items, gap_treatment="zero")
            m_symbol, circ_symbol = CACHED_PROFILES[(connection, scope)]
            checks = {
                m_symbol: dimensions["M"],
                "I_DIM": dimensions["I"],
                "C_DIM": dimensions["C"],
                circ_symbol: sum(dimensions.values()) / 3.0,
            }
            for symbol, calculated in checks.items():
                if not math.isclose(
                    _numeric(self.rows[symbol]), calculated,
                    rel_tol=tolerance, abs_tol=tolerance,
                ):
                    raise ValueError(
                        f"cached evidence derivation {symbol} no longer reconciles"
                    )

    def build_items(
        self, connection: str, replacement_scope: str
    ) -> tuple[EvidenceItem, ...]:
        factor_values = {
            "M_REV": {
                "low_reversibility": 0.0,
                "reversible_mechanical": 1.0,
            }.get(connection),
            "M_REP": {
                "assembly_level": 0.0,
                "component_level": 1.0,
            }.get(replacement_scope),
        }
        if factor_values["M_REV"] is None:
            raise ValueError(f"unknown connection factor: {connection}")
        if factor_values["M_REP"] is None:
            raise ValueError(f"unknown replacement-scope factor: {replacement_scope}")

        item_values = {**CENTRAL_ITEM_VALUES, **factor_values}
        items: list[EvidenceItem] = []
        for dimension, symbols in DIMENSION_ITEMS.items():
            for symbol in symbols:
                row = self.rows[symbol]
                state = EVIDENCE_STATES[symbol]
                items.append(
                    EvidenceItem(
                        symbol=symbol,
                        dimension=dimension,
                        value=float(item_values[symbol]),
                        evidence_state=state,
                        is_gap=state == "GAP",
                        status=row.status,
                        source_id=row.source_id,
                        source_sheet=row.source_sheet,
                        source_row=row.source_row,
                    )
                )
        return tuple(items)


def _dimension_means(
    items: Sequence[EvidenceItem], *, gap_treatment: str
) -> dict[str, float]:
    if gap_treatment not in {"zero", "exclude"}:
        raise ValueError("gap_treatment must be 'zero' or 'exclude'")
    dimensions: dict[str, float] = {}
    for dimension in ("M", "I", "C"):
        selected = [item for item in items if item.dimension == dimension]
        if gap_treatment == "exclude":
            selected = [item for item in selected if not item.is_gap]
        if not selected:
            raise ValueError(f"no evidence items remain in dimension {dimension}")
        dimensions[dimension] = sum(item.value for item in selected) / len(selected)
    return dimensions


@dataclass(frozen=True)
class CircularityResult:
    variant_id: str
    short_code: str
    mounting: str
    connection: str
    replacement_scope: str
    gap_treatment: str
    mechanistic: float
    institutional: float
    contextual: float
    combined: float
    items: tuple[EvidenceItem, ...]

    def as_record(self) -> dict[str, Any]:
        return {
            "id": self.variant_id,
            "short_code": self.short_code,
            "mounting": self.mounting,
            "connection": self.connection,
            "replacement_scope": self.replacement_scope,
            "gap_treatment": self.gap_treatment,
            "M": self.mechanistic,
            "I": self.institutional,
            "C": self.contextual,
            "CIRC": self.combined,
            "evidence_items": [item.as_record() for item in self.items],
        }


def run_circularity(
    variants: Sequence[Mapping[str, Any]],
    *,
    parameters: CircularityParameters | None = None,
    gap_treatment: str = "zero",
) -> list[CircularityResult]:
    """Attach the locked evidence-readiness dimensions to V01–V08."""

    parameters = parameters or CircularityParameters.from_locked_inputs()
    results: list[CircularityResult] = []
    for variant in variants:
        items = parameters.build_items(
            str(variant["connection"]), str(variant["replacement_scope"])
        )
        dimensions = _dimension_means(items, gap_treatment=gap_treatment)
        results.append(
            CircularityResult(
                variant_id=str(variant["id"]),
                short_code=str(variant["short_code"]),
                mounting=str(variant["mounting"]),
                connection=str(variant["connection"]),
                replacement_scope=str(variant["replacement_scope"]),
                gap_treatment=gap_treatment,
                mechanistic=dimensions["M"],
                institutional=dimensions["I"],
                contextual=dimensions["C"],
                combined=sum(dimensions.values()) / 3.0,
                items=items,
            )
        )
    return results


IMPLEMENTATION_STATUS = "IMPLEMENTED_EVIDENCE_GATE"
