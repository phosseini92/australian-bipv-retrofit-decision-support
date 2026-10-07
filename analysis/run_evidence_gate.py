"""Run the controlled PSCF-informed Evidence Gate; not the baseline."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.circularity import CircularityParameters, run_circularity  # noqa: E402
from src.config_loader import load_variants  # noqa: E402
from src.evidence_qa import evidence_qa_as_dicts, evaluate_evidence_assertions  # noqa: E402


DEFAULT_OUTPUT = ROOT / "outputs" / "tables" / "evidence_gate_qa.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def _repository_state() -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            capture_output=True, check=True,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True,
            capture_output=True, check=True,
        ).stdout.strip())
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}
    return {"commit": commit, "dirty": dirty}


def main() -> int:
    args = _parser().parse_args()
    variants = load_variants()["variants"]
    parameters = CircularityParameters.from_locked_inputs()
    central = run_circularity(variants, parameters=parameters, gap_treatment="zero")
    gap_excluded = run_circularity(
        variants, parameters=parameters, gap_treatment="exclude"
    )
    assertions = evaluate_evidence_assertions(
        central, gap_excluded, parameters
    )

    report = {
        "schema_version": "1.0",
        "gate": "PSCF_INFORMED_EVIDENCE_READINESS",
        "status": "PASS",
        "baseline_executed": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository": _repository_state(),
        "method_boundary": parameters.pscf_method_rule,
        "output_label": "PSCF-informed evidence-readiness",
        "coding_rule": parameters.evidence_code_rule,
        "missing_evidence_rule": parameters.missing_evidence_rule,
        "central_gap_treatment": "GAP items remain coded zero and are visibly flagged",
        "structural_gap_treatment": "Only GAP-labelled items are excluded from the relevant dimension denominator; explicit constraints remain zero",
        "central_variant_evidence": [item.as_record() for item in central],
        "gap_excluded_variant_evidence": [item.as_record() for item in gap_excluded],
        "assertions": evidence_qa_as_dicts(assertions),
        "scope_note": (
            "This gate validates item-level evidence coding and derived M, I, C, and combined structural-test values only. It does not run Pareto, sensitivity, break-even, or the formal baseline."
        ),
    }
    deterministic_payload = {
        key: value for key, value in report.items() if key != "generated_at_utc"
    }
    report["deterministic_content_sha256"] = sha256(json.dumps(
        deterministic_payload, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "PASS",
        "output": str(args.output),
        "assertions": [item.id for item in assertions],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
