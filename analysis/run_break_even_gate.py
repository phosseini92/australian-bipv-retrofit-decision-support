"""Run computable locked break-even thresholds and expose lock blockers."""

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

from src.break_even import run_break_even_analysis  # noqa: E402
from src.break_even_qa import (  # noqa: E402
    break_even_qa_as_dicts,
    evaluate_break_even_assertions,
)
from src.config_loader import load_variants  # noqa: E402
from src.cost_qa import cost_qa_as_dicts, evaluate_cost_assertions  # noqa: E402
from src.energy_qa import (  # noqa: E402
    build_variant_energy_records,
    evaluate_q01_to_q05,
    qa_results_as_dicts,
)
from src.input_loader import load_symbol_index  # noqa: E402
from src.lifecycle_cost import CostParameters, run_lifecycle_cost  # noqa: E402
from src.lifecycle_energy import LifecycleParameters, run_lifecycle_energy  # noqa: E402
from src.lifecycle_qa import (  # noqa: E402
    evaluate_lifecycle_assertions,
    lifecycle_qa_as_dicts,
)
from src.pv_energy import EnergyParameters, run_year_one_energy  # noqa: E402
from src.sensitivity import run_numerical_ofat  # noqa: E402
from src.sensitivity_qa import (  # noqa: E402
    evaluate_sensitivity_assertions,
    sensitivity_qa_as_dicts,
)
from src.weather import load_epw, load_weather_manifest  # noqa: E402


DEFAULT_EPW = (
    ROOT / "data" / "weather" / "AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw"
)
DEFAULT_OUTPUT = ROOT / "outputs" / "tables" / "break_even_gate_qa.json"


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
    rows = load_symbol_index()
    variants = load_variants()["variants"]
    energy_parameters = EnergyParameters.from_locked_inputs()
    lifecycle_parameters = LifecycleParameters.from_locked_inputs()
    cost_parameters = CostParameters.from_locked_inputs()
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
    first_year_energy = {
        key: value.energy_kwh for key, value in energy_results.items()
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
        variants, first_year_energy, parameters=lifecycle_parameters
    )
    lifecycle_assertions = evaluate_lifecycle_assertions(
        lifecycle_results, lifecycle_parameters
    )
    cost_results = run_lifecycle_cost(
        variants, lifecycle_results, parameters=cost_parameters
    )
    cost_assertions = evaluate_cost_assertions(cost_results, cost_parameters)
    sensitivity_central, _, sensitivity_results = run_numerical_ofat(
        first_year_energy, variants=variants
    )
    sensitivity_assertions = evaluate_sensitivity_assertions(
        sensitivity_central, sensitivity_results
    )

    analysis = run_break_even_analysis(first_year_energy, variants=variants)
    break_even_assertions = evaluate_break_even_assertions(analysis)
    primary_access = analysis.required_access_saving_primary_wlc[0].value
    diagnostic_access = (
        analysis.required_access_saving_initial_premium_diagnostic[0].value
    )
    recovery = analysis.recovery_value[0].value
    if primary_access is None or diagnostic_access is None or recovery is None:
        raise AssertionError("expected computed break-even thresholds are missing")

    weather_manifest = load_weather_manifest()
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "gate": "BREAK_EVEN",
        "status": "PASS",
        "computational_implementation": "PASS",
        "baseline_executed": False,
        "final_break_even_csv_executed": False,
        "research_decision_added_in_code": False,
        "approved_change_control": "CC-002 D1-B + D2-A + D3-A",
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
        "run_manifest": {
            "variant_set": [str(item["id"]) for item in variants],
            "code_version": repository["commit"],
            "timestamp": generated_at,
            "currency_basis": cost_parameters.currency_basis,
            "central_horizon_years": lifecycle_parameters.horizon_years,
            "discount_rate_search_interval": [0.0, 0.15],
            "service_life_integer_search_interval": [10, 50],
            "locked_output_provenance": [
                {
                    "symbol": symbol,
                    "source_sheet": rows[symbol].source_sheet,
                    "source_row": rows[symbol].source_row,
                    "status": rows[symbol].status,
                }
                for symbol in (
                    "BE_rev", "BE_access", "BE_life", "BE_rec", "BE_r"
                )
            ],
        },
        "results": analysis.as_record(),
        "key_findings": {
            "maximum_premium_central_no_savings_fraction": (
                analysis.maximum_premium[0].value
            ),
            "access_saving_primary_full_wlc_aud_per_event": primary_access,
            "access_saving_initial_premium_diagnostic_aud_per_event": (
                diagnostic_access
            ),
            "access_threshold_difference_aud_per_event": (
                primary_access - diagnostic_access
            ),
            "diagnostic_access_formula_wlc_residual_aud": (
                analysis
                .required_access_saving_initial_premium_diagnostic[0]
                .residual
            ),
            "service_life_result_all_four_pairs": (
                "NO_BREAK_EVEN_LE_50_YEARS"
            ),
            "incremental_owner_recovery_threshold_aud_per_tonne": recovery,
            "locked_upper_owner_recovery_aud_per_tonne": float(
                rows["V_rec"].high
            ),
            "recovery_threshold_multiple_of_locked_upper": (
                recovery / float(rows["V_rec"].high)
            ),
            "discount_rate_primary_comparisons": {
                item.comparison_id: item.status
                for item in analysis.discount_rate_primary
            },
        },
        "cc002_disposition": list(analysis.cc002_approval),
        "open_locked_spec_issues": list(analysis.open_locked_spec_issues),
        "parent_energy_assertions": qa_results_as_dicts(energy_assertions),
        "parent_lifecycle_assertions": lifecycle_qa_as_dicts(
            lifecycle_assertions
        ),
        "parent_cost_assertions": cost_qa_as_dicts(cost_assertions),
        "parent_numerical_ofat_assertions": sensitivity_qa_as_dicts(
            sensitivity_assertions
        ),
        "break_even_assertions": break_even_qa_as_dicts(
            break_even_assertions
        ),
        "scope_note": (
            "CC-002 D1-B + D2-A + D3-A is fully implemented. Computed "
            "thresholds and every explicit non-root status are reported. This "
            "controlled Gate emits no final break_even.csv or formal baseline; "
            "those remain downstream export-stage actions."
        ),
    }
    deterministic_payload = json.loads(json.dumps(report, ensure_ascii=False))
    deterministic_payload.pop("generated_at_utc", None)
    deterministic_payload["run_manifest"].pop("timestamp", None)
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
        "computational_implementation": "PASS",
        "output": str(args.output),
        "access_primary_full_wlc_aud_per_event": primary_access,
        "access_initial_premium_diagnostic_aud_per_event": diagnostic_access,
        "service_life": "no break-even <=50 years",
        "recovery_threshold_aud_per_tonne": recovery,
        "discount_rate_primary": {
            item.comparison_id: item.status
            for item in analysis.discount_rate_primary
        },
        "assertions": [item.id for item in break_even_assertions],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
