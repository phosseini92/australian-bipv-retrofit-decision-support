"""Run the controlled lifecycle-energy integration gate; not the baseline."""

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
from src.energy_qa import (  # noqa: E402
    build_variant_energy_records,
    evaluate_q01_to_q05,
    qa_results_as_dicts,
)
from src.input_loader import load_symbol_index  # noqa: E402
from src.lifecycle_energy import (  # noqa: E402
    LifecycleParameters,
    run_lifecycle_energy,
)
from src.lifecycle_qa import (  # noqa: E402
    evaluate_lifecycle_assertions,
    lifecycle_qa_as_dicts,
)
from src.pv_energy import EnergyParameters, run_year_one_energy  # noqa: E402
from src.weather import load_epw, load_weather_manifest  # noqa: E402


DEFAULT_EPW = (
    ROOT
    / "data"
    / "weather"
    / "AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw"
)
DEFAULT_OUTPUT = ROOT / "outputs" / "tables" / "lifecycle_energy_gate_qa.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epw", type=Path, default=DEFAULT_EPW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def _repository_state() -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}
    return {"commit": commit, "dirty": dirty}


def _float_input(rows, symbol: str) -> float:
    return float(rows[symbol].central)


def main() -> int:
    args = _parser().parse_args()
    rows = load_symbol_index()
    energy_parameters = EnergyParameters.from_locked_inputs()
    lifecycle_parameters = LifecycleParameters.from_locked_inputs()
    variants = load_variants()["variants"]
    weather = load_epw(args.epw)
    azimuth = _float_input(rows, "γ_N")

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
            "A_BIPV_m2": _float_input(rows, "A_BIPV"),
            "PVtech": str(rows["PVtech"].central),
            "Pdc0_kWp": energy_parameters.pdc0_kwp,
            "INV": str(rows["INV"].central),
            "Pac0_kW": energy_parameters.pac0_kw,
        },
    )
    energy_assertions = evaluate_q01_to_q05(
        energy_records,
        energy_results,
        pac0_kw=energy_parameters.pac0_kw,
    )

    lifecycle_results = run_lifecycle_energy(
        variants,
        {
            mounting: result.energy_kwh
            for mounting, result in energy_results.items()
        },
        parameters=lifecycle_parameters,
    )
    lifecycle_assertions = evaluate_lifecycle_assertions(
        lifecycle_results,
        lifecycle_parameters,
    )

    trajectories: dict[str, list[dict[str, float | int]]] = {}
    for result in lifecycle_results:
        key = f"{result.mounting}__{result.replacement_scope}"
        trajectories.setdefault(
            key,
            [
                {
                    "year": item.year,
                    "degradation_factor": item.degradation_factor,
                    "E_y_degraded_kwh": item.energy_degraded_kwh,
                    "availability_factor": item.availability_factor,
                    "E_y_net_kwh": item.energy_net_kwh,
                }
                for item in result.annual
            ],
        )

    weather_manifest = load_weather_manifest()
    report = {
        "schema_version": "1.0",
        "gate": "DEGRADATION_AVAILABILITY_LIFECYCLE_ENERGY",
        "status": "PASS",
        "baseline_executed": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository": _repository_state(),
        "controlled_weather": {
            "filename": args.epw.name,
            "sha256": weather.source_sha256,
            "records": len(weather.data),
            "normalization": weather.normalization,
            "nominal_package_period": weather_manifest[
                "nominal_package_period"
            ],
            "epw_header_period_of_record": weather_manifest[
                "epw_header_period_of_record"
            ],
            "evidence_note": weather_manifest["evidence_note"],
        },
        "runtime": {
            package: version(package)
            for package in ("numpy", "pandas", "pvlib", "scipy")
        },
        "parameters": {
            "T_years": lifecycle_parameters.horizon_years,
            "d_linear_per_year": (
                lifecycle_parameters.annual_degradation_rate
            ),
            "A_BIPV_m2": lifecycle_parameters.bipv_area_m2,
            "N_mod_eq": lifecycle_parameters.equivalent_module_count,
            "lambda_mod_per_module_year": (
                lifecycle_parameters.module_failure_rate_per_year
            ),
            "f_fail_events_per_year": (
                lifecycle_parameters.failure_rate_events_per_year
            ),
            "N_fail_expected": (
                lifecycle_parameters.locked_expected_failure_events
            ),
            "DT_event_hours": lifecycle_parameters.downtime_hours_per_event,
            "N_replace_per_event": (
                lifecycle_parameters.replaced_module_equivalents_per_event
            ),
            "N_handle_component": (
                lifecycle_parameters.component_handled_module_equivalents
            ),
            "N_handle_assembly": (
                lifecycle_parameters.assembly_handled_module_equivalents
            ),
            "A_dist_component_m2": (
                lifecycle_parameters.component_disturbed_area_m2
            ),
            "A_dist_assembly_m2": (
                lifecycle_parameters.assembly_disturbed_area_m2
            ),
            "k_rev_time": lifecycle_parameters.reversibility_time_factor,
            "SL_inv_years": lifecycle_parameters.inverter_service_life_years,
            "module_mass_kg": lifecycle_parameters.module_mass_kg,
            "module_mass_derivation": (
                "locked M_EOL * 1000 / locked N_mod,eq"
            ),
        },
        "year_one_energy_kwh": {
            mounting: result.energy_kwh
            for mounting, result in energy_results.items()
        },
        "variant_lifecycle": [
            result.as_record() for result in lifecycle_results
        ],
        "annual_trajectories": trajectories,
        "parent_energy_assertions": qa_results_as_dicts(energy_assertions),
        "lifecycle_assertions": lifecycle_qa_as_dicts(lifecycle_assertions),
        "scope_note": (
            "This gate validates lifecycle energy and intervention burden only; "
            "whole-life cost, PSCF, Pareto, break-even, sensitivity, and the "
            "formal baseline remain disabled. Q08 here validates the common "
            "inverter schedule prerequisite; its cost allowance is rechecked "
            "in the future cost gate."
        ),
    }
    deterministic_payload = {
        key: value for key, value in report.items() if key != "generated_at_utc"
    }
    report["deterministic_content_sha256"] = sha256(
        json.dumps(
            deterministic_payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "output": str(args.output),
                "assertions": [
                    item.id for item in energy_assertions + lifecycle_assertions
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
