"""Hard-fail Q01–Q05 checks for the controlled energy integration gate."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class QaResult:
    id: str
    status: str
    evidence: str


def _runtime():
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - exercised only before setup
        raise RuntimeError(
            "The energy runtime is not installed. Install requirements.txt first."
        ) from exc
    return np


def build_variant_energy_records(
    variants: list[dict[str, Any]],
    energy_results: dict[str, Any],
    common_inputs: dict[str, Any],
) -> list[dict[str, Any]]:
    """Attach mounting-only energy results to the locked variant matrix."""

    records: list[dict[str, Any]] = []
    for variant in variants:
        mounting = variant["mounting"]
        result = energy_results[mounting]
        records.append(
            {
                **variant,
                **common_inputs,
                "E1_thermal_kwh": float(result.energy_kwh),
                "max_p_ac_kw": float(result.hourly["p_ac_w"].max() / 1000.0),
            }
        )
    return records


def evaluate_q01_to_q05(
    records: list[dict[str, Any]],
    energy_results: dict[str, Any],
    *,
    pac0_kw: float,
    tolerance: float = 1e-9,
) -> list[QaResult]:
    """Evaluate locked energy assertions and raise if any assertion fails."""

    np = _runtime()
    results: list[QaResult] = []

    common_fields = ("A_BIPV_m2", "PVtech", "Pdc0_kWp", "INV", "Pac0_kW")
    common_ok = all(len({record[field] for record in records}) == 1 for field in common_fields)
    results.append(
        QaResult(
            "Q01",
            "PASS" if common_ok else "FAIL",
            "A_BIPV, PV technology, nominal DC capacity, inverter family, and AC rating are identical across V01–V08.",
        )
    )

    q02_ok = True
    q02_groups: dict[str, list[float]] = {"direct": [], "ventilated": []}
    for record in records:
        q02_groups[record["mounting"]].append(record["E1_thermal_kwh"])
    for values in q02_groups.values():
        q02_ok &= max(values) - min(values) <= tolerance
    results.append(
        QaResult(
            "Q02",
            "PASS" if q02_ok else "FAIL",
            "V01–V04 share one direct-mount energy result and V05–V08 share one ventilated result.",
        )
    )

    q03_ok = True
    for mounting in ("direct", "ventilated"):
        for scope in ("assembly_level", "component_level"):
            values = [
                record["E1_thermal_kwh"]
                for record in records
                if record["mounting"] == mounting
                and record["replacement_scope"] == scope
            ]
            q03_ok &= max(values) - min(values) <= tolerance
    results.append(
        QaResult(
            "Q03",
            "PASS" if q03_ok else "FAIL",
            "Changing connection reversibility changes no first-year electrical result.",
        )
    )

    q04_ok = True
    for mounting in ("direct", "ventilated"):
        for connection in ("low_reversibility", "reversible_mechanical"):
            values = [
                record["E1_thermal_kwh"]
                for record in records
                if record["mounting"] == mounting
                and record["connection"] == connection
            ]
            q04_ok &= max(values) - min(values) <= tolerance
    results.append(
        QaResult(
            "Q04",
            "PASS" if q04_ok else "FAIL",
            "Changing replacement scope changes no first-year thermal/electrical result.",
        )
    )

    q05_ok = True
    q05_details: list[str] = []
    nonnegative_columns = (
        "ghi",
        "dni",
        "dhi",
        "poa_direct",
        "poa_sky_diffuse",
        "poa_ground_diffuse",
        "poa_global",
        "poa_direct_effective",
        "poa_sky_effective",
        "poa_ground_effective",
        "effective_irradiance",
        "p_dc_gross_w",
        "p_dc_net_w",
        "p_ac_w",
    )
    for mounting, result in energy_results.items():
        frame = result.hourly
        values = frame[list(nonnegative_columns)].to_numpy(dtype=float)
        finite = bool(np.isfinite(values).all())
        nonnegative = bool((values >= -tolerance).all())
        max_ac_kw = float(frame["p_ac_w"].max() / 1000.0)
        bounded = max_ac_kw <= pac0_kw + tolerance
        energy_nonnegative = bool(np.isfinite(result.energy_kwh) and result.energy_kwh >= 0.0)
        q05_ok &= finite and nonnegative and bounded and energy_nonnegative
        q05_details.append(
            f"{mounting}: max AC={max_ac_kw:.9f} kW, E1={result.energy_kwh:.6f} kWh"
        )
    results.append(
        QaResult(
            "Q05",
            "PASS" if q05_ok else "FAIL",
            "; ".join(q05_details)
            + f"; all audited energy arrays finite/non-negative and limit={pac0_kw:.6f} kW.",
        )
    )

    failed = [result.id for result in results if result.status != "PASS"]
    if failed:
        raise AssertionError(f"energy QA failed: {failed}")
    return results


def qa_results_as_dicts(results: list[QaResult]) -> list[dict[str, str]]:
    return [asdict(result) for result in results]
