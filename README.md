# Australian BIPV Retrofit Decision Support

Repository v0.1 implements the first controlled milestone for the APSRC study
*Beyond Energy Yield: Lifecycle Value and Circularity Readiness of Australian
BIPV Retrofits*.

## Repo v0.1 audit and integration-gate status

This version contains:

- the exact V01–V08 full-factorial mapping;
- machine-readable exports of Input Table blocks A–F and the Sources Register;
- cell-level provenance, formula text, and cached workbook values;
- the locked execution order, sensitivity contract, Pareto criteria, output names,
  and Q01–Q14 QA assertions;
- module boundaries and analysis entry points; and
- structural tests for the locked research contract.

The v0.1 structure and locked-input contract have been formally audited. The
hourly energy chain is implemented and validated with the controlled EPW through
Perez-Driesse POA, physical beam/diffuse IAM, mounting-specific SAPM cell
temperature, PVWatts DC, the locked loss stack, inverter conversion, clipping,
and year-one AC-energy integration.

The energy-only integration gate has passed Q01–Q05. Direct-mount year-one AC
energy is 161,751.981 kWh and ventilated-mount energy is 166,904.081 kWh for the
locked north orientation.

The subsequent degradation → availability → lifecycle-energy gate has also
passed. It applies the locked linear degradation equation, expected-event
availability approximation, disturbed-area and handled-scope burdens, one
permanently replaced product per event, material replacement mass, and the
common scheduled inverter years.

The lifecycle-cost and replacement-bookkeeping gate has passed as well. It
implements initial mounting and reversibility cost, annual O&M, expected
corrective material replacement, the common reference inverter allowance,
end-of-life recycling/recovery rules, end-of-year discounting, WLC, and WLC per
lifetime kWh. Unsupported access and removal tariffs remain excluded from the
central accounting and reserved for break-even analysis. These are
gate-validation results, not a completed baseline.

The PSCF-informed Evidence Gate has now passed too. Item-level evidence is
carried into mechanistic, institutional, and contextual dimensions without
presenting the study-specific 0/0.5/1 coding as a native PSCF score. The
structural GAP run excludes only items explicitly labelled `GAP`; documented
constraints remain zero. Institutional and contextual values are common across
all variants, and mounting creates no evidence-readiness difference.

The central primary Pareto Gate has also passed. It evaluates the seven locked
raw criteria in their stated directions, without weights or normalization, and
uses only an eight-ULP tolerance to suppress floating-point noise. The central
non-dominated set is V02, V04, V06, and V08.

The locked criterion-structure and evidence-gap robustness gate has passed as
well. The full primary/combined-CIRC × GAP-zero/excluded matrix retains the
same non-dominated set and the same six dominance edges in all four scenarios;
each scenario has Jaccard similarity 1.0 to the central-primary set. Numerical
OFAT sensitivity, break-even, and the formal baseline remain disabled.

## Controlled sources

The repository snapshot is derived only from:

1. `APSRC_Research_Design_v2.0_LOCK.docx`
2. `APSRC_Input_Table_v1.0_F_LOCK.xlsx`
3. `APSRC_Analysis_Specification_v1.0_LOCK.docx`

Their SHA-256 digests are recorded in
`data/inputs/source_manifest.yaml`. The binary source documents are not copied
into the repository; the CSV exports retain workbook sheet and row locators.

The controlled EPW is validated against `data/weather/weather_manifest.json`
and remains Git-ignored. `docs/change_control/CC-001-tmyx-index-and-evidence-period.md`
records the approved mixed-year calendar normalisation and the discrepancy
between the nominal 2011–2025 package label and the header-reported 2011–2015
station record.

## Install and validate

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python analysis/run_energy_gate.py
.venv/bin/python analysis/run_lifecycle_energy_gate.py
.venv/bin/python analysis/run_cost_gate.py
.venv/bin/python analysis/run_evidence_gate.py
.venv/bin/python analysis/run_pareto_gate.py
.venv/bin/python analysis/run_pareto_robustness_gate.py
```

`requirements-lock.txt` records the fully resolved environment used for the
formal audit and integration-gate tests.

The baseline, sensitivity, Pareto, and break-even entry points continue to fail
closed until the downstream implementation gates pass. The authorised numerical
runners at this stage are the energy, lifecycle-energy, cost, Evidence, central
primary Pareto, and Pareto robustness Gates; none is the formal baseline.

## Repository map

- `config/`: locked variants, schema, model, sensitivity, and QA contract.
- `data/inputs/`: machine-readable controlled-input snapshot and provenance.
- `src/`: validation utilities, the implemented energy chain, and downstream
  locked module boundaries.
- `analysis/`: guarded future entry points.
- `tests/`: lock-integrity and static QA tests.
- `docs/`: methodology, source, assumption-status, and scope notes.
- `outputs/`: reserved locked output locations; gate QA artifacts are explicitly
  marked as non-baseline.

## Change control

Research-design, input, equation, execution-order, decision-rule, and output
changes require a new controlled source version and an explicit impact review.
Code organization may change, but the locked analysis contract must not change
silently.
