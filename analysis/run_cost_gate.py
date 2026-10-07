"""Run the controlled lifecycle-cost integration gate; not the baseline."""

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
from src.cost_qa import cost_qa_as_dicts, evaluate_cost_assertions  # noqa: E402
from src.energy_qa import (  # noqa: E402
    build_variant_energy_records,
    evaluate_q01_to_q05,
    qa_results_as_dicts,
)
from src.input_loader import load_symbol_index  # noqa: E402
from src.lifecycle_cost import CostParameters, run_lifecycle_cost  # noqa: E402
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
DEFAULT_OUTPUT = ROOT / "outputs" / "tables" / "cost_gate_qa.json"


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
    variants = load_variants()["variants"]
    energy_parameters = EnergyParameters.from_locked_inputs()
    lifecycle_parameters = LifecycleParameters.from_locked_inputs()
    cost_parameters = CostParameters.from_locked_inputs()
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
    cost_results = run_lifecycle_cost(
        variants,
        lifecycle_results,
        parameters=cost_parameters,
    )
    cost_assertions = evaluate_cost_assertions(
        cost_results,
        cost_parameters,
    )

    cashflow_schedules: dict[str, list[dict[str, float | int]]] = {}
    for result in cost_results:
        key = f"{result.mounting}__{result.connection}"
        cashflow_schedules.setdefault(
            key,
            [
                {
                    "year": item.year,
                    "discount_factor": item.discount_factor,
                    "C_OM_aud": item.om_aud,
                    "C_corrective_material_aud": (
                        item.corrective_material_aud
                    ),
                    "C_access_aud": item.access_aud,
                    "C_inverter_aud": item.inverter_aud,
                    "C_EOL_net_aud": item.eol_net_aud,
                    "nominal_total_aud": item.nominal_total_aud,
                    "discounted_total_aud": item.discounted_total_aud,
                }
                for item in result.annual
            ],
        )

    weather_manifest = load_weather_manifest()
    status_symbols = (
        "r",
        "C_BIPV",
        "C_direct",
        "p_vent",
        "C_vent",
        "p_rev",
        "ΔC_rev",
        "m_OM",
        "p_invrep",
        "C_rep,mat",
        "C_extra,asm",
        "C_access",
        "C_rec",
        "V_rec",
        "D_trans_cost",
        "C_EOL,rem",
    )
    report = {
        "schema_version": "1.0",
        "gate": "LIFECYCLE_COST_AND_REPLACEMENT_BOOKKEEPING",
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
            "currency_basis": cost_parameters.currency_basis,
            "T_years": cost_parameters.horizon_years,
            "real_discount_rate": cost_parameters.real_discount_rate,
            "A_BIPV_m2": cost_parameters.bipv_area_m2,
            "A_module_m2": cost_parameters.module_area_m2,
            "C_BIPV_aud_per_m2": (
                cost_parameters.reference_bipv_cost_per_m2
            ),
            "C_direct_aud_per_m2": (
                cost_parameters.direct_mount_cost_per_m2
            ),
            "p_vent": cost_parameters.ventilated_complexity_factor,
            "C_vent_aud_per_m2": (
                cost_parameters.ventilated_mount_cost_per_m2
            ),
            "p_rev": cost_parameters.reversibility_premium_factor,
            "DeltaC_rev_aud_per_m2": (
                cost_parameters.reversibility_premium_per_m2
            ),
            "m_OM": cost_parameters.annual_om_rate,
            "f_fail_events_per_year": (
                cost_parameters.failure_rate_events_per_year
            ),
            "C_rep_material_aud_per_event": (
                cost_parameters.failed_product_material_cost_per_event_aud
            ),
            "C_extra_assembly_aud_per_event": (
                cost_parameters.assembly_extra_material_cost_per_event_aud
            ),
            "C_access_aud_per_event_central": (
                cost_parameters.central_access_cost_per_event_aud
            ),
            "C_access_basis": (
                "excluded from central accounting; solved in break-even"
            ),
            "p_invrep": cost_parameters.inverter_replacement_factor,
            "inverter_replacement_years": list(
                cost_results[0].inverter_replacement_years
            ),
            "M_EOL_tonnes": cost_parameters.eol_pv_mass_tonnes,
            "C_recycling_aud_per_tonne": (
                cost_parameters.recycling_service_cost_per_tonne_aud
            ),
            "C_EOL_recycling_aud": cost_parameters.eol_recycling_cost_aud,
            "C_EOL_transport_component_aud": (
                cost_parameters.transport_component_aud
            ),
            "C_EOL_processing_component_aud": (
                cost_parameters.processing_component_aud
            ),
            "V_owner_aud": cost_parameters.total_owner_recovery_credit_aud,
            "C_EOL_removal_aud_central": (
                cost_parameters.central_eol_removal_cost_aud
            ),
            "C_EOL_removal_basis": (
                "excluded from central accounting; solved in break-even/stress"
            ),
            "separate_transport_rule": (
                cost_parameters.separate_transport_rule
            ),
        },
        "input_statuses": {
            symbol: {
                "status": rows[symbol].status,
                "source_sheet": rows[symbol].source_sheet,
                "source_row": rows[symbol].source_row,
            }
            for symbol in status_symbols
        },
        "variant_cost": [result.as_record() for result in cost_results],
        "annual_cashflow_schedules": cashflow_schedules,
        "parent_energy_assertions": qa_results_as_dicts(energy_assertions),
        "parent_lifecycle_assertions": lifecycle_qa_as_dicts(
            lifecycle_assertions
        ),
        "cost_assertions": cost_qa_as_dicts(cost_assertions),
        "scope_note": (
            "This gate validates central lifecycle-cost and replacement-cost "
            "bookkeeping only. Electricity is not monetised. Unsupported "
            "access and removal tariffs remain break-even variables. PSCF, "
            "Pareto, break-even, sensitivity, and the formal baseline remain "
            "disabled."
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
                "assertions": [item.id for item in cost_assertions],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
