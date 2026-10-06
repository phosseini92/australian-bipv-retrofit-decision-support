# Australian BIPV Retrofit Decision Support

Repository v0.1 implements the first controlled milestone for the APSRC study
*Beyond Energy Yield: Lifecycle Value and Circularity Readiness of Australian
BIPV Retrofits*.

## Repo v0.1 audit and energy-gate status

This version contains:

- the exact V01–V08 full-factorial mapping;
- machine-readable exports of Input Table blocks A–F and the Sources Register;
- cell-level provenance, formula text, and cached workbook values;
- the locked execution order, sensitivity contract, Pareto criteria, output names,
  and Q01–Q14 QA assertions;
- module boundaries and analysis entry points; and
- structural tests for the locked research contract.

The v0.1 structure and locked-input contract have been formally audited. The
hourly energy chain is now implemented and unit-tested through EPW validation,
Perez-Driesse POA, physical beam/diffuse IAM, mounting-specific SAPM cell
temperature, PVWatts DC, the locked loss stack, inverter conversion, clipping,
and year-one AC-energy integration.

Baseline simulation remains intentionally disabled. The exact locked EPW is not
present, and lifecycle/decision modules remain skeletons. No baseline result has
been generated.

## Controlled sources

The repository snapshot is derived only from:

1. `APSRC_Research_Design_v2.0_LOCK.docx`
2. `APSRC_Input_Table_v1.0_F_LOCK.xlsx`
3. `APSRC_Analysis_Specification_v1.0_LOCK.docx`

Their SHA-256 digests are recorded in
`data/inputs/source_manifest.yaml`. The binary source documents are not copied
into the repository; the CSV exports retain workbook sheet and row locators.

## Install and validate

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

`requirements-lock.txt` records the fully resolved environment used for the
formal audit and energy-module tests.

The four analysis entry points continue to fail closed until the EPW gate and
downstream implementation gates are passed.

## Repository map

- `config/`: locked variants, schema, model, sensitivity, and QA contract.
- `data/inputs/`: machine-readable controlled-input snapshot and provenance.
- `src/`: validation utilities, the implemented energy chain, and downstream
  locked module boundaries.
- `analysis/`: guarded future entry points.
- `tests/`: lock-integrity and static QA tests.
- `docs/`: methodology, source, assumption-status, and scope notes.
- `outputs/`: reserved locked output locations; no simulation results are present.

## Change control

Research-design, input, equation, execution-order, decision-rule, and output
changes require a new controlled source version and an explicit impact review.
Code organization may change, but the locked analysis contract must not change
silently.
