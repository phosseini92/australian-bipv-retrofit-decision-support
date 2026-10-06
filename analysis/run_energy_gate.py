"""Run the controlled energy-only integration gate; this is not the baseline."""

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
from src.pv_energy import EnergyParameters, run_year_one_energy  # noqa: E402
from src.weather import load_epw, load_weather_manifest  # noqa: E402


DEFAULT_EPW = (
    ROOT
    / "data"
    / "weather"
    / "AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw"
)
DEFAULT_OUTPUT = ROOT / "outputs" / "tables" / "energy_gate_qa.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epw", type=Path, default=DEFAULT_EPW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def _float_input(rows, symbol: str) -> float:
    return float(rows[symbol].central)


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


def main() -> int:
    args = _parser().parse_args()
    rows = load_symbol_index()
    parameters = EnergyParameters.from_locked_inputs()
    weather = load_epw(args.epw)
    azimuth = _float_input(rows, "γ_N")

    energy_results = {
        mounting: run_year_one_energy(
            weather,
            mounting=mounting,
            surface_azimuth=azimuth,
            parameters=parameters,
        )
        for mounting in ("direct", "ventilated")
    }
    common_inputs = {
        "A_BIPV_m2": _float_input(rows, "A_BIPV"),
        "PVtech": str(rows["PVtech"].central),
        "Pdc0_kWp": parameters.pdc0_kwp,
        "INV": str(rows["INV"].central),
        "Pac0_kW": parameters.pac0_kw,
    }
    variants = load_variants()["variants"]
    records = build_variant_energy_records(variants, energy_results, common_inputs)
    assertions = evaluate_q01_to_q05(
        records,
        energy_results,
        pac0_kw=parameters.pac0_kw,
    )

    metrics = {}
    for mounting, result in energy_results.items():
        frame = result.hourly
        metrics[mounting] = {
            "E1_thermal_kwh": result.energy_kwh,
            "max_p_ac_kw": float(frame["p_ac_w"].max() / 1000.0),
            "clipping_hours_at_pac0": int(
                (frame["p_ac_w"] >= parameters.pac0_kw * 1000.0 - 1e-6).sum()
            ),
            "effective_irradiance_kwh_per_m2": float(
                frame["effective_irradiance"].sum()
                * weather.timestep_hours
                / 1000.0
            ),
            "mean_cell_temperature_c": float(
                frame[f"temp_cell_{mounting}"].mean()
            ),
            "max_cell_temperature_c": float(
                frame[f"temp_cell_{mounting}"].max()
            ),
        }

    weather_manifest = load_weather_manifest()
    report = {
        "schema_version": "1.0",
        "gate": "ENERGY_INTEGRATION_Q01_Q05",
        "status": "PASS",
        "baseline_executed": False,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository": _repository_state(),
        "weather": {
            "filename": args.epw.name,
            "sha256": weather.source_sha256,
            "records": len(weather.data),
            "metadata": weather.metadata,
            "normalization": weather.normalization,
            "nominal_package_period": weather_manifest["nominal_package_period"],
            "epw_header_period_of_record": weather_manifest[
                "epw_header_period_of_record"
            ],
            "evidence_note": weather_manifest["evidence_note"],
            "required_field_ranges": {
                column: {
                    "min": float(weather.data[column].min()),
                    "max": float(weather.data[column].max()),
                    "missing": int(weather.data[column].isna().sum()),
                }
                for column in ("temp_air", "wind_speed", "ghi", "dni", "dhi")
            },
        },
        "runtime": {
            package: version(package)
            for package in ("numpy", "pandas", "pvlib", "scipy")
        },
        "orientation": {"name": "North", "surface_azimuth_deg": azimuth},
        "parameters": {
            "surface_tilt_deg": parameters.surface_tilt,
            "albedo": parameters.albedo,
            "n_IAM": parameters.refractive_index,
            "K_IAM_per_m": parameters.extinction_coefficient,
            "L_IAM_m": parameters.glass_thickness,
            "Pdc0_kWp": parameters.pdc0_kwp,
            "gamma_pdc_per_c": parameters.gamma_pdc,
            "L_sys": parameters.system_loss_fraction,
            "Pac0_kW": parameters.pac0_kw,
            "eta_inv_nom": parameters.eta_inv_nom,
            "direct_proxy": parameters.direct_proxy,
            "ventilated_proxy": parameters.ventilated_proxy,
        },
        "mounting_metrics": metrics,
        "variant_energy": records,
        "assertions": qa_results_as_dicts(assertions),
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
    print(json.dumps({"status": "PASS", "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
