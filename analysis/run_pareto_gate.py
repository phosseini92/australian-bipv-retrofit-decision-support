"""Run the controlled central primary Pareto Gate; not the baseline."""

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
from src.config_loader import load_variants  # noqa: E402
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
from src.lifecycle_qa import evaluate_lifecycle_assertions, lifecycle_qa_as_dicts  # noqa: E402
from src.pareto import (  # noqa: E402
    FLOAT_TOLERANCE_ULPS,
    analyze_pareto,
    load_primary_criteria,
)
from src.pareto_qa import evaluate_pareto_assertions, pareto_qa_as_dicts  # noqa: E402
from src.pv_energy import EnergyParameters, run_year_one_energy  # noqa: E402
from src.weather import load_epw, load_weather_manifest  # noqa: E402


DEFAULT_EPW = (
    ROOT / "data" / "weather" / "AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw"
)
DEFAULT_OUTPUT = ROOT / "outputs" / "tables" / "pareto_gate_qa.json"


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
    rows = load_symbol_index()
    variants = load_variants()["variants"]
    energy_parameters = EnergyParameters.from_locked_inputs()
    lifecycle_parameters = LifecycleParameters.from_locked_inputs()
    cost_parameters = CostParameters.from_locked_inputs()
    circularity_parameters = CircularityParameters.from_locked_inputs()
    weather = load_epw(args.epw)
    azimuth = float(rows["γ_N"].central)

    energy_results = {
        mounting: run_year_one_energy(
            weather,
            mounting=mounting,
            surface_azimuth=azimuth,
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

    lifecycle_results = run_lifecycle_energy(
        variants,
        {key: value.energy_kwh for key, value in energy_results.items()},
        parameters=lifecycle_parameters,
    )
    lifecycle_assertions = evaluate_lifecycle_assertions(
        lifecycle_results, lifecycle_parameters
    )
    cost_results = run_lifecycle_cost(
        variants, lifecycle_results, parameters=cost_parameters
    )
    cost_assertions = evaluate_cost_assertions(cost_results, cost_parameters)
    evidence_results = run_circularity(
        variants, parameters=circularity_parameters, gap_treatment="zero"
    )
    gap_excluded_results = run_circularity(
        variants, parameters=circularity_parameters, gap_treatment="exclude"
    )
    evidence_assertions = evaluate_evidence_assertions(
        evidence_results, gap_excluded_results, circularity_parameters
    )

    decision_records: list[dict[str, Any]] = []
    for variant, life, cost, evidence in zip(
        variants, lifecycle_results, cost_results, evidence_results
    ):
        if not (
            variant["id"] == life.variant_id == cost.variant_id == evidence.variant_id
        ):
            raise AssertionError("variant alignment changed across parent gates")
        decision_records.append({
            **variant,
            "E_life": life.net_lifetime_energy_kwh,
            "A_life": life.lifetime_availability_ratio,
            "WLC": cost.whole_life_cost_aud,
            "B_dist": life.intervention.disturbed_area_burden_m2_event,
            "M": evidence.mechanistic,
            "I": evidence.institutional,
            "C": evidence.contextual,
            "CIRC": evidence.combined,
            "CostIntensity_aud_per_kwh": cost.cost_intensity_aud_per_kwh,
        })

    criteria = load_primary_criteria()
    pareto = analyze_pareto(
        decision_records,
        criteria=criteria,
        tolerance_ulps=FLOAT_TOLERANCE_ULPS,
    )
    pareto_assertions = evaluate_pareto_assertions(decision_records, pareto)
    outcome_index = {item.variant_id: item for item in pareto.outcomes}
    central_table = [
        {**record, **outcome_index[str(record["id"])].as_record()}
        for record in decision_records
    ]

    weather_manifest = load_weather_manifest()
    report = {
        "schema_version": "1.0",
        "gate": "CENTRAL_PRIMARY_PARETO_DOMINANCE",
        "status": "PASS",
        "baseline_executed": False,
        "sensitivity_executed": False,
        "criterion_structure_robustness_executed": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository": _repository_state(),
        "controlled_weather": {
            "filename": args.epw.name,
            "sha256": weather.source_sha256,
            "records": len(weather.data),
            "nominal_package_period": weather_manifest["nominal_package_period"],
            "epw_header_period_of_record": weather_manifest["epw_header_period_of_record"],
            "evidence_note": weather_manifest["evidence_note"],
        },
        "runtime": {
            package: version(package)
            for package in ("numpy", "pandas", "pvlib", "scipy")
        },
        "dominance_rule": (
            "a is no worse than b in every directed raw criterion and strictly better in at least one"
        ),
        "weights": None,
        "normalization": None,
        "floating_tolerance": {
            "ulps": FLOAT_TOLERANCE_ULPS,
            "use": "floating_point_noise_only",
        },
        "criteria": [
            {"field": item.field, "direction": item.direction}
            for item in criteria
        ],
        "constant_criteria": {
            "I": evidence_results[0].institutional,
            "C": evidence_results[0].contextual,
            "note": "Retained for conceptual fidelity; no variant differences fabricated.",
        },
        "central_decision_table": central_table,
        "dominance_pairs": [item.as_record() for item in pareto.dominance_pairs],
        "non_dominated_set": list(pareto.non_dominated_ids),
        "parent_energy_assertions": qa_results_as_dicts(energy_assertions),
        "parent_lifecycle_assertions": lifecycle_qa_as_dicts(lifecycle_assertions),
        "parent_cost_assertions": cost_qa_as_dicts(cost_assertions),
        "parent_evidence_assertions": evidence_qa_as_dicts(evidence_assertions),
        "pareto_assertions": pareto_qa_as_dicts(pareto_assertions),
        "scope_note": (
            "This gate executes only the central seven-criterion primary Pareto dominance analysis. Combined-circularity, GAP-treatment, OFAT sensitivity, break-even, final locked CSV outputs, figures, and the formal baseline remain disabled."
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
        "non_dominated_set": list(pareto.non_dominated_ids),
        "dominance_edges": len(pareto.dominance_pairs),
        "assertions": [item.id for item in pareto_assertions],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
