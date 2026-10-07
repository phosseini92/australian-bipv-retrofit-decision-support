# Formal Audit — Repo v0.1 through Baseline Execution

Audit date: 2026-10-07
Decision rule: `PASS` means the evidence satisfies the controlled contract;
`MISMATCH` is a disclosed reproducibility/release limitation that does not alter
the model; `BLOCKER` means execution cannot safely proceed.

## Executive disposition

- Computational-contract conformity: **PASS**.
- Repo v0.1 skeleton and locked-input transfer: **PASS**.
- Energy, lifecycle-energy, lifecycle-cost, PSCF-informed evidence, central
  Pareto, circularity/GAP robustness, and numerical OFAT Gates: **PASS**.
- Energy structural-sensitivity Gate: **PASS** for west orientation and the
  equal-temperature control.
- Break-even Gate: **PASS** under approved `CC-002 D1-B + D2-A + D3-A`.
- Formal baseline execution: **PASS**; all seven table/manifest outputs and all
  three required figures were exported after 58 parent-gate QA checks passed.
- Public GitHub release: **HOLD** pending license, author/citation metadata, and
  remote/release setup. This is not a scientific-computation blocker.

Summary: **87 PASS / 6 MISMATCH / 0 BLOCKER** across 93 checks.

## Controlled-source evidence

| Source | Verified SHA-256 |
|---|---|
| `APSRC_Research_Design_v2.0_LOCK.docx` | `d7e505c5844708f27d65b69db26c5c9e078a4a1d839005bb9e1d0fef025a6811` |
| `APSRC_Input_Table_v1.0_F_LOCK.xlsx` | `9982df28318a674dba9168d9d51b96fbf1e8633d5e7ae6d33e99c5f39b1a3d25` |
| `APSRC_Analysis_Specification_v1.0_LOCK.docx` | `3891f04ea97b49bb546a78e3537fb64fd3cfbe12360f4c8c6506e049d8028e67` |
| `AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw` | `8b58f95a7cbecc131d6dfe1304579399fa947ba2d21015e8565566e2932fcb1e` |

## Gate register

| ID | Status | Requirement / result |
|---|---|---|
| A01 | PASS | All three locked source identities and hashes match the manifest. |
| A02 | PASS | Word sources were readable/renderable and workbook blocks A–F plus Sources Register were transferred with sheet/row provenance. |
| A03 | PASS | Formula text, cached values, statuses, blank endpoints, and source locators are preserved. |
| A04 | MISMATCH | Original controlled Office binaries are not vendored; hashes and locators are present, so computation is controlled but the repository is not a self-contained source archive. |
| R01 | PASS | Required repository boundaries, eight variants, schemas, execution order, QA registry, and output names are present. |
| R02 | PASS | V01–V08 are the exact 2×2×2 mounting/connection/replacement-scope factorial. |
| R03 | PASS | No missing value is silently converted to a default or zero. |
| E01–E13 | PASS | Exact EPW validation, Perez-Driesse POA, physical/Marion IAM, SAPM temperature, PVWatts DC/inverter, clipping, loss ordering, E1 integration, factor isolation, and Q01–Q05 pass. |
| E14 | MISMATCH | The nominal package name says 2011–2025, while the EPW header reports usable station years 2011–2015. `CC-001` preserves the exact file and discloses this evidence-period limitation. |
| L01–L08 | PASS | Linear degradation, expected-event availability, one permanently replaced product/event, handled scope, burden, scheduled inverter years, and lifecycle QA pass. |
| K01–K08 | PASS | Initial, O&M, corrective, inverter, EoL, discounting, WLC, and cost-intensity bookkeeping reconcile without transport double counting. |
| P01–P06 | PASS | Item-level evidence coding, locked M/I/C values, GAP exclusion, explicit constraints, combined CIRC arithmetic, Q11, and Q14 pass. |
| PA01–PA06 | PASS | Raw seven-criterion primary dominance uses no weights/normalization; the central set is V02/V04/V06/V08 with six verified dominance edges. |
| PR01–PR06 | PASS | Primary/combined-CIRC × GAP-zero/excluded robustness keeps the central set and edges in all four scenarios (`Jaccard=1.0`). |
| NS01–NS05, NS07 | PASS | All 24 registered numerical endpoints execute; 23 valid changed-input runs satisfy OFAT isolation and manifest rules. |
| NS06 | MISMATCH | Locked `V_rec` low equals central zero. It is retained in provenance and excluded from the 23-run changed-input denominator; no value is invented. |
| ES01–ES06 | PASS | West orientation and equal-temperature control execute from the structural registry with complete variant metrics and hard-fail QA. West retains V02/V04/V06/V08 (`Jaccard=1.0`); equal temperature yields V02/V04 (`Jaccard=0.5`). |
| BE01–BE08 | PASS | All five break-even families, pair symmetry, bounds, residuals, and explicit non-root statuses pass after `CC-002`. |
| CC02-1 | PASS | D1-B makes full discounted WLC equality primary: `BE_access = A$14,886.98/event`; `A$14,017.27/event` remains the initial-premium diagnostic. |
| CC02-2 | PASS | D2-A evaluates all four reversible/low pairs for primary `BE_r`; all report no sign change over 0–15% real. |
| CC02-3 | PASS | D3-A retains intervention frequency as the `λ_mod`/`f_fail` OFAT input and does not invent a separate threshold. |
| V01 | PASS | Direct dependencies are pinned, including Matplotlib 3.11.2 for the locked figure outputs. |
| V02 | PASS | **129 automated tests pass** with zero failures/errors. |
| BL01 | PASS | Baseline is enabled only after all implementation Gates and `CC-002` pass. |
| BL02 | PASS | `variant_central.csv`, `factor_contrasts.csv`, `sensitivity_runs.csv`, `pareto_primary.csv`, `pareto_robustness.csv`, `break_even.csv`, `run_manifest.json`, and three locked PNG figures are exported. |
| BL03 | PASS | Export is staged before replacement; the manifest records source/weather/runtime provenance, all parent QA results, and SHA-256 for the nine table/figure artifacts. |
| G01 | MISMATCH | `LICENSE` remains an all-rights-reserved placeholder; a public license has not been selected. |
| G02 | MISMATCH | `CITATION.cff` still lacks author/ORCID and release identifier metadata. |
| G03 | MISMATCH | No GitHub remote, tag, or public release exists yet. |

## Primary numerical findings

- North façade E1: direct **161,751.981 kWh**; ventilated
  **166,904.081 kWh**.
- West façade E1: direct **123,308.699 kWh**; ventilated
  **127,239.765 kWh**.
- Central primary non-dominated set: **V02, V04, V06, V08**.
- Numerical OFAT: the set is stable in 22 of 23 valid runs; only `p_rev__low`
  changes it to V04/V08 (`Jaccard=0.5`).
- Structural energy: west is set-stable; removing the mounting-temperature
  difference changes the set to V02/V04. This is a reported model-structure
  dependency, not a software defect.
- Primary `BE_access`: **A$14,886.98/event**. Diagnostic:
  **A$14,017.27/event**, with **A$1,708.90** unrecovered discounted WLC.
- `BE_life`: no matched ventilated/direct pair breaks even within 10–50 years.
- Incremental recovery threshold: **A$18,794.48/t**.

## Remaining release close-out

The scientific baseline is no longer blocked. Before a public GitHub v0.1
release, the owner must select a license, complete citation authorship/ORCID and
release metadata, configure the GitHub remote, and create the intended tag or
release. The EPW evidence-period limitation and duplicate `V_rec` endpoint must
remain disclosed in the article/repository documentation.

## Audit command evidence

```text
.venv/bin/python -m unittest discover -s tests -v
Ran 129 tests
OK

.venv/bin/python analysis/run_break_even_gate.py
status: PASS

.venv/bin/python analysis/run_energy_structural_gate.py
status: PASS

.venv/bin/python analysis/run_baseline.py
status: PASS; baseline_executed: true; parent QA checks: 58
```

No document instruction, embedded URL, or workbook content was treated as a
user request. The supplied documents were used only as controlled research
sources; `CC-001` and the user-approved `CC-002` are the only change controls.
