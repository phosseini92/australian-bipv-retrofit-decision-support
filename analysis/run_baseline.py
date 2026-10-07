"""Run and atomically export the complete locked formal baseline."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".matplotlib-cache"))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
import pandas as pd  # noqa: E402

from src.baseline import BaselineAnalysis, run_formal_baseline  # noqa: E402
from src.config_loader import load_model, load_variants  # noqa: E402
from src.sensitivity import pareto_inclusion_frequencies  # noqa: E402
from src.weather import load_epw, load_weather_manifest  # noqa: E402


DEFAULT_EPW = (
    ROOT / "data" / "weather" / "AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw"
)
TABLE_DIR = ROOT / "outputs" / "tables"
FIGURE_DIR = ROOT / "outputs" / "figures"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epw", type=Path, default=DEFAULT_EPW)
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


def _json_cell(value: Any) -> Any:
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    frame = pd.DataFrame([
        {key: _json_cell(value) for key, value in row.items()}
        for row in rows
    ])
    frame.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")


def _primary_rows(analysis: BaselineAnalysis) -> list[dict[str, Any]]:
    outcomes = {item.variant_id: item for item in analysis.primary_pareto.outcomes}
    return [
        {
            **record,
            "is_non_dominated": outcomes[str(record["id"])].is_non_dominated,
            "dominated_by": list(outcomes[str(record["id"])].dominated_by),
            "dominates": list(outcomes[str(record["id"])].dominates),
        }
        for record in analysis.central_records
    ]


def _sensitivity_rows(analysis: BaselineAnalysis) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in analysis.numerical_ofat:
        summary = result.summary_record()
        for record in result.variant_records:
            rows.append({"run_type": "numerical_ofat", **summary, **record})
    for scenario in analysis.energy_structural:
        if scenario.scenario_id == "central":
            continue
        for record in scenario.variant_records:
            rows.append({
                "run_type": "energy_structural",
                "run_id": scenario.scenario_id,
                "changed_parameter": scenario.input_symbol,
                "level": "structural",
                "value": scenario.setting,
                "non_dominated_set": list(scenario.pareto.non_dominated_ids),
                "jaccard_to_central": scenario.jaccard_to_central,
                "is_valid_sensitivity_run": True,
                "exclusion_reason": None,
                **record,
            })
    for scenario in analysis.circularity_robustness:
        records = (
            analysis.central_records
            if scenario.gap_treatment == "zero"
            else analysis.gap_excluded_records
        )
        for record in records:
            rows.append({
                "run_type": "circularity_structure",
                "run_id": scenario.scenario_id,
                "changed_parameter": "CRIT/GAP_RULE",
                "level": "structural",
                "value": (
                    f"{scenario.criterion_structure};"
                    f"gap_{scenario.gap_treatment}"
                ),
                "non_dominated_set": list(
                    scenario.analysis.non_dominated_ids
                ),
                "jaccard_to_central": scenario.jaccard_to_central_primary,
                "is_valid_sensitivity_run": True,
                "exclusion_reason": None,
                **record,
            })
    return rows


def _robustness_rows(analysis: BaselineAnalysis) -> list[dict[str, Any]]:
    rows = [
        {
            "run_type": "circularity_structure",
            "scenario_id": scenario.scenario_id,
            "criterion_structure": scenario.criterion_structure,
            "gap_treatment": scenario.gap_treatment,
            "non_dominated_set": list(scenario.analysis.non_dominated_ids),
            "dominance_edges": len(scenario.analysis.dominance_pairs),
            "jaccard_to_central": scenario.jaccard_to_central_primary,
        }
        for scenario in analysis.circularity_robustness
    ]
    rows.extend(
        {
            "run_type": "energy_structural",
            "scenario_id": scenario.scenario_id,
            "criterion_structure": "primary",
            "gap_treatment": "zero",
            "non_dominated_set": list(scenario.pareto.non_dominated_ids),
            "dominance_edges": len(scenario.pareto.dominance_pairs),
            "jaccard_to_central": scenario.jaccard_to_central,
        }
        for scenario in analysis.energy_structural
        if scenario.scenario_id != "central"
    )
    return rows


def _plot_energy_cost(path: Path, analysis: BaselineAnalysis) -> None:
    non_dominated = set(analysis.primary_pareto.non_dominated_ids)
    label_offsets = {
        "V01": (-28, -18), "V02": (5, 5),
        "V03": (-28, -18), "V04": (5, 5),
        "V05": (-28, -18), "V06": (5, 5),
        "V07": (-28, -18), "V08": (5, 5),
    }
    fig, ax = plt.subplots(figsize=(8.2, 5.2), constrained_layout=True)
    for record in analysis.central_records:
        variant_id = str(record["id"])
        selected = variant_id in non_dominated
        ax.scatter(
            record["WLC"] / 1000.0,
            record["E_life"] / 1_000_000.0,
            s=92 if selected else 58,
            marker="o" if selected else "x",
            color="#0072B2" if selected else "#777777",
            linewidth=1.5, zorder=3 if selected else 4,
        )
        ax.annotate(
            variant_id,
            (record["WLC"] / 1000.0, record["E_life"] / 1_000_000.0),
            xytext=label_offsets[variant_id], textcoords="offset points",
            fontsize=8,
        )
    ax.set_xlabel("Whole-life cost (A$ thousand; lower is better)")
    ax.set_ylabel("Lifetime electricity (GWh; higher is better)")
    ax.set_title("Central energy–cost view of the primary Pareto result")
    ax.margins(x=0.05, y=0.08)
    ax.grid(alpha=0.22)
    ax.legend(
        handles=[
            Line2D([], [], marker="o", linestyle="", color="#0072B2",
                   markersize=7, label="Non-dominated (seven criteria)"),
            Line2D([], [], marker="x", linestyle="", color="#777777",
                   markersize=7, label="Dominated"),
        ],
        loc="lower right", frameon=False, fontsize=8,
    )
    fig.savefig(path, dpi=220, metadata={"Software": "APSRC baseline"})
    plt.close(fig)


def _plot_stability(path: Path, analysis: BaselineAnalysis) -> None:
    ids = [str(record["id"]) for record in analysis.central_records]
    frequencies = pareto_inclusion_frequencies(analysis.numerical_ofat, ids)
    structural = _robustness_rows(analysis)
    fig, axes = plt.subplots(
        2, 1, figsize=(9.0, 7.0), constrained_layout=True,
        gridspec_kw={"height_ratios": [1.15, 1.0]},
    )
    axes[0].bar(ids, [frequencies[item] for item in ids], color="#009E73")
    axes[0].set_ylim(0, 1.05)
    axes[0].set_ylabel("OFAT inclusion frequency")
    axes[0].set_title("Pareto stability across 23 valid numerical OFAT runs")
    axes[0].grid(axis="y", alpha=0.22)
    labels = [str(row["scenario_id"]).replace("_", "\n") for row in structural]
    values = [float(row["jaccard_to_central"]) for row in structural]
    colors = ["#56B4E9"] * 4 + ["#E69F00"] * 2
    axes[1].bar(labels, values, color=colors)
    axes[1].set_ylim(0, 1.05)
    axes[1].set_ylabel("Jaccard similarity")
    axes[1].set_title("Structural-set similarity to central primary")
    axes[1].grid(axis="y", alpha=0.22)
    axes[1].tick_params(axis="x", labelsize=7)
    axes[1].legend(
        handles=[
            Patch(facecolor="#56B4E9", label="Criterion/GAP structure"),
            Patch(facecolor="#E69F00", label="Energy structure"),
        ],
        loc="lower left", frameon=False, fontsize=8,
    )
    fig.savefig(path, dpi=220, metadata={"Software": "APSRC baseline"})
    plt.close(fig)


def _plot_break_even(path: Path, analysis: BaselineAnalysis) -> None:
    primary = analysis.break_even.required_access_saving_primary_wlc[0]
    diagnostic = analysis.break_even.required_access_saving_initial_premium_diagnostic[0]
    if primary.value is None or diagnostic.value is None or diagnostic.residual is None:
        raise AssertionError("access thresholds are required for the figure")
    slope = diagnostic.residual / (primary.value - diagnostic.value)
    x = [primary.value * index / 100.0 * 1.2 for index in range(101)]
    y = [slope * (primary.value - value) / 1000.0 for value in x]
    fig, ax = plt.subplots(figsize=(8.2, 5.2), constrained_layout=True)
    ax.plot(x, y, color="#0072B2", linewidth=2.2)
    ax.axhline(0.0, color="#222222", linewidth=1.0)
    ax.axvline(
        primary.value, color="#009E73", linestyle="--", linewidth=1.7,
        label=f"Primary full-WLC equality: A${primary.value:,.2f}/event",
    )
    ax.axvline(
        diagnostic.value, color="#D55E00", linestyle=":", linewidth=1.7,
        label=f"Initial-premium diagnostic: A${diagnostic.value:,.2f}/event",
    )
    ax.set_xlabel("Access/intervention saving (A$/event)")
    ax.set_ylabel("Remaining reversible-minus-low WLC (A$ thousand)")
    ax.set_title("CC-002 primary access break-even threshold")
    ax.grid(alpha=0.22)
    ax.legend(frameon=False, fontsize=8)
    fig.savefig(path, dpi=220, metadata={"Software": "APSRC baseline"})
    plt.close(fig)


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = _parser().parse_args()
    model = load_model()
    if not model["simulation_enabled"]:
        raise RuntimeError("formal baseline is not enabled in config/model.yaml")
    weather = load_epw(args.epw)
    analysis = run_formal_baseline(weather)
    repository = _repository_state()
    generated_at = datetime.now(timezone.utc).isoformat()
    expected = set(model["locked_output_filenames"])
    table_names = {
        "variant_central.csv", "factor_contrasts.csv", "sensitivity_runs.csv",
        "pareto_primary.csv", "pareto_robustness.csv", "break_even.csv",
    }
    figure_names = {
        "fig_energy_cost_pareto.png", "fig_dominance_stability.png",
        "fig_break_even.png",
    }
    if expected != table_names | figure_names | {"run_manifest.json"}:
        raise AssertionError("locked output filename contract changed")

    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="baseline-stage-", dir=ROOT / "outputs") as raw:
        stage = Path(raw)
        _write_csv(stage / "variant_central.csv", analysis.central_records)
        _write_csv(stage / "factor_contrasts.csv", analysis.factor_contrasts)
        _write_csv(stage / "sensitivity_runs.csv", _sensitivity_rows(analysis))
        _write_csv(stage / "pareto_primary.csv", _primary_rows(analysis))
        _write_csv(stage / "pareto_robustness.csv", _robustness_rows(analysis))
        _write_csv(
            stage / "break_even.csv",
            [item.as_record() for item in analysis.break_even.all_numeric_results()],
        )
        _plot_energy_cost(stage / "fig_energy_cost_pareto.png", analysis)
        _plot_stability(stage / "fig_dominance_stability.png", analysis)
        _plot_break_even(stage / "fig_break_even.png", analysis)

        artifact_hashes = {
            name: _sha256(stage / name)
            for name in sorted(table_names | figure_names)
        }
        manifest = {
            "schema_version": "1.0",
            "run_type": "FORMAL_BASELINE",
            "status": "PASS",
            "generated_at_utc": generated_at,
            "repository": repository,
            "variant_set": [str(item["id"]) for item in load_variants()["variants"]],
            "approved_change_controls": ["CC-001", "CC-002"],
            "research_decision_added_in_code": False,
            "weather": {
                **load_weather_manifest(),
                "observed_sha256": weather.source_sha256,
                "records": len(weather.data),
            },
            "runtime": {
                package: version(package)
                for package in ("numpy", "pandas", "pvlib", "scipy", "matplotlib")
            },
            "qa_by_gate": analysis.qa_by_gate,
            "all_qa_passed": True,
            "central_non_dominated_set": list(analysis.primary_pareto.non_dominated_ids),
            "cc002_primary_access_aud_per_event": (
                analysis.break_even.required_access_saving_primary_wlc[0].value
            ),
            "artifact_sha256": artifact_hashes,
        }
        (stage / "run_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        for name in sorted(table_names):
            os.replace(stage / name, TABLE_DIR / name)
        for name in sorted(figure_names):
            os.replace(stage / name, FIGURE_DIR / name)
        os.replace(stage / "run_manifest.json", TABLE_DIR / "run_manifest.json")

    print(json.dumps({
        "status": "PASS",
        "baseline_executed": True,
        "tables": sorted(table_names | {"run_manifest.json"}),
        "figures": sorted(figure_names),
        "central_non_dominated_set": list(analysis.primary_pareto.non_dominated_ids),
        "cc002_primary_access_aud_per_event": (
            analysis.break_even.required_access_saving_primary_wlc[0].value
        ),
        "qa_checks": sum(len(items) for items in analysis.qa_by_gate.values()),
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
