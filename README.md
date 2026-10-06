# Australian BIPV Retrofit Decision Support

Repository v0.1 implements the first controlled milestone for the APSRC study
*Beyond Energy Yield: Lifecycle Value and Circularity Readiness of Australian
BIPV Retrofits*.

## Milestone 0.1 status

This version contains:

- the exact V01–V08 full-factorial mapping;
- machine-readable exports of Input Table blocks A–F and the Sources Register;
- cell-level provenance, formula text, and cached workbook values;
- the locked execution order, sensitivity contract, Pareto criteria, output names,
  and Q01–Q14 QA assertions;
- module boundaries and analysis entry points; and
- structural tests for the locked research contract.

Numerical simulation is intentionally disabled. The energy, lifecycle, cost,
PSCF-informed evidence, Pareto, sensitivity, and break-even modules are skeletons
until this milestone is reviewed and accepted.

## Controlled sources

The repository snapshot is derived only from:

1. `APSRC_Research_Design_v2.0_LOCK.docx`
2. `APSRC_Input_Table_v1.0_F_LOCK.xlsx`
3. `APSRC_Analysis_Specification_v1.0_LOCK.docx`

Their SHA-256 digests are recorded in
`data/inputs/source_manifest.yaml`. The binary source documents are not copied
into the repository; the CSV exports retain workbook sheet and row locators.

## Validate milestone 0.1

The validation suite uses the Python standard library:

```bash
python -m unittest discover -s tests -v
```

The four analysis entry points fail closed in this milestone. Running one prints
an explicit message that simulation is disabled.

## Repository map

- `config/`: locked variants, schema, model, sensitivity, and QA contract.
- `data/inputs/`: machine-readable controlled-input snapshot and provenance.
- `src/`: validation utilities plus locked module boundaries.
- `analysis/`: guarded future entry points.
- `tests/`: lock-integrity and static QA tests.
- `docs/`: methodology, source, assumption-status, and scope notes.
- `outputs/`: reserved locked output locations; no results are present in v0.1.

## Change control

Research-design, input, equation, execution-order, decision-rule, and output
changes require a new controlled source version and an explicit impact review.
Code organization may change, but the locked analysis contract must not change
silently.
