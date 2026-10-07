"""Run the locked numerical OFAT Sensitivity Gate; not the baseline."""

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

from src.circularity import CircularityParameters, run_circularity  # noqa: E402
from src.config_loader import load_sensitivity, load_variants  # noqa: E402
from src.cost_qa import cost_qa_as_dicts, evaluate_cost_assertions  # noqa: E402
from src.energy_qa import (  # noqa: E402
    build_variant_energy_records,
    evaluate_q01_to_q05,
    qa_results_as_dicts,
)
from src.evidence_qa import evidence_qa_as_dicts, evaluate_evidence_assertions  # noqa: E402
from src.input_loader import load_symbol_index  # noqa: E402
from src.lifecycle_cost import CostParameters, run_lifecycle_cost  # noqa: E402
from src.lifecycle_energy import LifecycleParameters, run_lifecycle_energy  # noqa: E402
from src.lifecycle_qa import (  # noqa: E402
    evaluate_lifecycle_assertions,
    lifecycle_qa_as_dicts,
)
from src.pareto_qa import evaluate_pareto_assertions, pareto_qa_as_dicts  # noqa: E402
from src.pv_energy import EnergyParameters, run_year_one_energy  # noqa: E402
from src.sensitivity import (  # noqa: E402
    pareto_inclusion_frequencies,
    run_numerical_ofat,
)
from src.sensitivity_qa import (  # noqa: E402
    evaluate_sensitivity_assertions,
    sensitivity_qa_as_dicts,
)
from src.weather import load_epw, load_weather_manifest  # noqa: E402


DEFAULT_EPW = (
    ROOT / "data" / "weather" / "AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw"
)
DEFAULT_OUTPUT = (
    ROOT / "outputs" / "tables" / "numerical_ofat_sensitivity_gate_qa.json"
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


def _manifest(
    result: Any,
    *,
    variant_ids: list[str],
    code_version: str | None,
    timestamp: str,
) -> dict[str, Any]:
    definition = result.definition
    return {
        "run_id": definition.run_id,
        "changed_parameter": definition.changed_parameter,
        "level": definition.level,
        "source_sheet": definition.source_sheet,
        "source_row": definition.source_row,
        "value": definition.value,
        "variant_set": variant_ids,
        "code_version": code_version,
        "timestamp": timestamp,
        "is_valid_sensitivity_run": result.is_valid_sensitivity_run,
        "exclusion_reason": result.exclusion_reason,
    }


def _deterministic_payload(report: dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(json.dumps(report, ensure_ascii=False))
    payload.pop("generated_at_utc", None)
    for manifest in payload["run_manifests"]:
        manifest.pop("timestamp", None)
    return payload


def main() -> int:
    args = _parser().parse_args()
    generated_at = datetime.now(timezone.utc).isoformat()
    repository = _repository_state()
    rows = load_symbol_index()
    variants = load_variants()["variants"]
    variant_ids = [str(item["id"]) for item in variants]
    energy_parameters = EnergyParameters.from_locked_inputs()
    lifecycle_parameters = LifecycleParameters.from_locked_inputs()
    cost_parameters = CostParameters.from_locked_inputs()
    circularity_parameters = CircularityParameters.from_locked_inputs()
    weather = load_epw(args.epw)

    energy_results = {
        mounting: run_year_one_energy(
            weather,
            mounting=mounting,
            surface_azimuth=float(rows["γ_N"].central),
            parameters=energy_parameters,
        )
        for mounting in ("direct", "ventilated")
    }
    energy_records = build_variant_energy_records(
        variants,
        energy_results,
        {
            "A_BIPV_m2": float(rows["A_BIPV"].central),
            "PVtech": str(rows["PVtech"].central),
            "Pdc0_kWp": energy_parameters.pdc0_kwp,
            "INV": str(rows["INV"].central),
            "Pac0_kW": energy_parameters.pac0_kw,
        },
    )
    energy_assertions = evaluate_q01_to_q05(
        energy_records, energy_results, pac0_kw=energy_parameters.pac0_kw
    )

    first_year_energy = {
        key: value.energy_kwh for key, value in energy_results.items()
    }
    lifecycle_results = run_lifecycle_energy(
        variants, first_year_energy, parameters=lifecycle_parameters
    )
    lifecycle_assertions = evaluate_lifecycle_assertions(
        lifecycle_results, lifecycle_parameters
    )
    cost_results = run_lifecycle_cost(
        variants, lifecycle_results, parameters=cost_parameters
    )
    cost_assertions = evaluate_cost_assertions(cost_results, cost_parameters)
    central_evidence = run_circularity(
        variants, parameters=circularity_parameters, gap_treatment="zero"
    )
    excluded_evidence = run_circularity(
        variants, parameters=circularity_parameters, gap_treatment="exclude"
    )
    evidence_assertions = evaluate_evidence_assertions(
        central_evidence, excluded_evidence, circularity_parameters
    )

    central_records, central_pareto, results = run_numerical_ofat(
        first_year_energy,
        variants=variants,
    )
    central_pareto_assertions = evaluate_pareto_assertions(
        central_records, central_pareto
    )
    sensitivity_assertions = evaluate_sensitivity_assertions(
        central_records, results
    )
    valid_results = [item for item in results if item.is_valid_sensitivity_run]
    excluded_results = [
        item for item in results if not item.is_valid_sensitivity_run
    ]
    inclusion = pareto_inclusion_frequencies(results, variant_ids)
    inclusion_counts = {
        variant_id: sum(
            variant_id in item.pareto.non_dominated_ids
            for item in valid_results
        )
        for variant_id in variant_ids
    }
    contract = load_sensitivity()
    required_manifest_fields = set(contract["required_run_manifest_fields"])
    manifests = [
        _manifest(
            item,
            variant_ids=variant_ids,
            code_version=repository["commit"],
            timestamp=generated_at,
        )
        for item in results
    ]
    if not all(required_manifest_fields <= set(item) for item in manifests):
        raise AssertionError("required sensitivity manifest fields are missing")

    weather_manifest = load_weather_manifest()
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "gate": "NUMERICAL_OFAT_SENSITIVITY",
        "status": "PASS",
        "baseline_executed": False,
        "numerical_sensitivity_executed": True,
        "structural_sensitivity_executed": False,
        "break_even_executed": False,
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
        "execution_rule": contract["execution_rule"],
        "registered_numerical_inputs": contract["numerical_inputs"],
        "registered_endpoint_evaluations": len(results),
        "valid_changed_input_runs": len(valid_results),
        "excluded_duplicate_endpoints": [
            {
                "run_id": item.definition.run_id,
                "value": item.definition.value,
                "reason": item.exclusion_reason,
            }
            for item in excluded_results
        ],
        "central_primary_non_dominated_set": list(
            central_pareto.non_dominated_ids
        ),
        "pareto_inclusion": {
            variant_id: {
                "count": inclusion_counts[variant_id],
                "denominator": len(valid_results),
                "frequency": inclusion[variant_id],
            }
            for variant_id in variant_ids
        },
        "stability": {
            "minimum_jaccard_to_central": min(
                item.jaccard_to_central for item in valid_results
            ),
            "runs_with_changed_pareto_set": [
                item.definition.run_id
                for item in valid_results
                if item.pareto.non_dominated_ids
                != central_pareto.non_dominated_ids
            ],
            "jaccard_is_set_similarity_not_probability": True,
            "inclusion_frequency_is_robustness_summary_not_probability": True,
        },
        "run_manifests": manifests,
        "run_summaries": [item.summary_record() for item in results],
        "sensitivity_variant_results": [
            {
                "run_id": item.definition.run_id,
                "variants": list(item.variant_records),
            }
            for item in results
        ],
        "parent_energy_assertions": qa_results_as_dicts(energy_assertions),
        "parent_lifecycle_assertions": lifecycle_qa_as_dicts(
            lifecycle_assertions
        ),
        "parent_cost_assertions": cost_qa_as_dicts(cost_assertions),
        "parent_evidence_assertions": evidence_qa_as_dicts(
            evidence_assertions
        ),
        "parent_central_pareto_assertions": pareto_qa_as_dicts(
            central_pareto_assertions
        ),
        "sensitivity_assertions": sensitivity_qa_as_dicts(
            sensitivity_assertions
        ),
        "scope_note": (
            "This gate executes only the 24 registered low/high numerical OFAT "
            "endpoints. V_rec low equals its central value and is executed but "
            "excluded from the 23-run changed-input denominator. No structural "
            "sensitivity, break-even calculation, locked final baseline CSV, "
            "figure, or formal baseline is produced."
        ),
    }
    report["deterministic_content_sha256"] = sha256(json.dumps(
        _deterministic_payload(report),
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
        "status": "PASS",
        "output": str(args.output),
        "registered_endpoint_evaluations": len(results),
        "valid_changed_input_runs": len(valid_results),
        "central_non_dominated_set": list(central_pareto.non_dominated_ids),
        "runs_with_changed_pareto_set": report["stability"][
            "runs_with_changed_pareto_set"
        ],
        "minimum_jaccard": report["stability"][
            "minimum_jaccard_to_central"
        ],
        "assertions": [item.id for item in sensitivity_assertions],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
