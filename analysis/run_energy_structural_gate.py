"""Run the two locked energy structural sensitivities and hard-fail QA."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config_loader import load_variants  # noqa: E402
from src.input_loader import load_symbol_index  # noqa: E402
from src.structural_sensitivity import (  # noqa: E402
    run_energy_structural_sensitivity,
)
from src.structural_sensitivity_qa import (  # noqa: E402
    energy_structural_qa_as_dicts,
    evaluate_energy_structural_assertions,
)
from src.weather import load_epw, load_weather_manifest  # noqa: E402


DEFAULT_EPW = (
    ROOT / "data" / "weather" / "AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw"
)
DEFAULT_OUTPUT = (
    ROOT / "outputs" / "tables" / "energy_structural_sensitivity_gate_qa.json"
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epw", type=Path, default=DEFAULT_EPW)
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
    generated_at = datetime.now(timezone.utc).isoformat()
    repository = _repository_state()
    variants = load_variants()["variants"]
    rows = load_symbol_index()
    weather = load_epw(args.epw)
    scenarios = run_energy_structural_sensitivity(weather, variants=variants)
    assertions = evaluate_energy_structural_assertions(scenarios)
    weather_manifest = load_weather_manifest()

    report: dict[str, Any] = {
        "schema_version": "1.0",
        "gate": "ENERGY_STRUCTURAL_SENSITIVITY",
        "status": "PASS",
        "baseline_executed": False,
        "research_decision_added_in_code": False,
        "generated_at_utc": generated_at,
        "repository": repository,
        "controlled_weather": {
            "filename": args.epw.name,
            "sha256": weather.source_sha256,
            "records": len(weather.data),
            "nominal_package_period": weather_manifest["nominal_package_period"],
            "epw_header_period_of_record": weather_manifest[
                "epw_header_period_of_record"
            ],
            "evidence_note": weather_manifest["evidence_note"],
        },
        "runtime": {
            package: version(package)
            for package in ("numpy", "pandas", "pvlib", "scipy")
        },
        "run_manifest": [
            {
                "changed_parameter": scenario.input_symbol,
                "source_sheet": rows[scenario.input_symbol].source_sheet,
                "source_row": rows[scenario.input_symbol].source_row,
                "value": scenario.setting,
                "variant_set": [str(item["id"]) for item in variants],
                "code_version": repository["commit"],
                "timestamp": generated_at,
            }
            for scenario in scenarios
            if scenario.scenario_id != "central"
        ],
        "results": [scenario.as_record() for scenario in scenarios],
        "assertions": energy_structural_qa_as_dicts(assertions),
        "scope_note": (
            "This Gate executes only the two registered energy structural "
            "sensitivities: west orientation and equal-temperature control. "
            "It introduces no new weather, thermal, cost, or decision assumption."
        ),
    }
    deterministic_payload = json.loads(json.dumps(report, ensure_ascii=False))
    deterministic_payload.pop("generated_at_utc", None)
    for item in deterministic_payload["run_manifest"]:
        item.pop("timestamp", None)
    report["deterministic_content_sha256"] = sha256(json.dumps(
        deterministic_payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["status"],
        "output": str(args.output),
        "scenarios": {
            scenario.scenario_id: {
                "energy_kwh": scenario.first_year_energy_kwh,
                "non_dominated_set": list(scenario.pareto.non_dominated_ids),
                "jaccard_to_central": scenario.jaccard_to_central,
            }
            for scenario in scenarios
        },
        "assertions": [item.id for item in assertions],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
