"""Load and validate the machine-readable snapshot of the locked workbook."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_ROOT / "data" / "inputs"
INPUT_FILES = (
    "building.csv",
    "pv_electrical.csv",
    "lifecycle.csv",
    "costs.csv",
    "pscf_evidence.csv",
    "sensitivity.csv",
)
ALLOWED_STATUSES = {"LOCKED", "DERIVED", "PROVISIONAL", "STRUCTURAL TEST"}
REQUIRED_COLUMNS = {
    "parameter",
    "symbol",
    "unit",
    "central",
    "low",
    "high",
    "central_formula",
    "low_formula",
    "high_formula",
    "source_id",
    "evidence_type",
    "applies_to",
    "status",
    "rationale",
    "notes",
    "source_sheet",
    "source_row",
}


def parse_scalar(value: str):
    """Return ``None``, ``Decimal``, or source text without guessing units."""

    if value == "":
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return value


@dataclass(frozen=True)
class InputRow:
    parameter: str
    symbol: str
    unit: str
    central: object
    low: object
    high: object
    central_formula: str
    low_formula: str
    high_formula: str
    source_id: str
    evidence_type: str
    applies_to: str
    status: str
    rationale: str
    notes: str
    source_sheet: str
    source_row: int


def iter_input_rows(filename: str) -> Iterator[InputRow]:
    path = INPUT_DIR / filename
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if set(reader.fieldnames or ()) != REQUIRED_COLUMNS:
            missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
            extra = set(reader.fieldnames or ()) - REQUIRED_COLUMNS
            raise ValueError(f"{filename}: schema mismatch; missing={missing}, extra={extra}")
        for record in reader:
            if record["status"] not in ALLOWED_STATUSES:
                raise ValueError(f"{filename}:{record['source_row']}: invalid status")
            for field in ("parameter", "symbol", "unit", "source_id", "evidence_type", "applies_to", "rationale", "source_sheet"):
                if not record[field]:
                    raise ValueError(f"{filename}:{record['source_row']}: blank {field}")
            yield InputRow(
                parameter=record["parameter"],
                symbol=record["symbol"],
                unit=record["unit"],
                central=parse_scalar(record["central"]),
                low=parse_scalar(record["low"]),
                high=parse_scalar(record["high"]),
                central_formula=record["central_formula"],
                low_formula=record["low_formula"],
                high_formula=record["high_formula"],
                source_id=record["source_id"],
                evidence_type=record["evidence_type"],
                applies_to=record["applies_to"],
                status=record["status"],
                rationale=record["rationale"],
                notes=record["notes"],
                source_sheet=record["source_sheet"],
                source_row=int(record["source_row"]),
            )


def load_symbol_index() -> dict[str, InputRow]:
    """Return the first occurrence of each symbol in source-block order."""

    index: dict[str, InputRow] = {}
    for filename in INPUT_FILES:
        for row in iter_input_rows(filename):
            index.setdefault(row.symbol, row)
    return index
