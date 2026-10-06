# Formal Audit — Repo v0.1 and Energy Implementation Gate

Audit date: 2026-10-06  
Audit scope: repository structure, controlled inputs, locked variant/design
contract, QA registration, energy-module implementation, and readiness to run.  
Decision rule: `PASS` means evidence satisfies the locked contract;
`MISMATCH` means a non-scientific repository/release gap exists; `BLOCKER`
means execution cannot safely proceed.

## Executive disposition

- Computational-contract conformity: **PASS** — no new research assumption or
  silent change to a locked input, equation, variant, decision rule, or output
  contract was identified. One weather evidence-description mismatch is
  disclosed separately.
- Repo v0.1 skeleton gate: **PASS**.
- Energy implementation gate: **PASS** — controlled EPW integration and Q01–Q05
  pass.
- Baseline-execution gate: **BLOCKED** — no baseline was run.
- Public GitHub-release gate: **HOLD** — license, citation authorship, and remote
  repository metadata remain unresolved.

Summary: **28 PASS / 5 MISMATCH / 1 BLOCKER** across 34 checks.

## Controlled-source evidence

| Source | Verified SHA-256 |
|---|---|
| `APSRC_Research_Design_v2.0_LOCK.docx` | `d7e505c5844708f27d65b69db26c5c9e078a4a1d839005bb9e1d0fef025a6811` |
| `APSRC_Input_Table_v1.0_F_LOCK.xlsx` | `9982df28318a674dba9168d9d51b96fbf1e8633d5e7ae6d33e99c5f39b1a3d25` |
| `APSRC_Analysis_Specification_v1.0_LOCK.docx` | `3891f04ea97b49bb546a78e3537fb64fd3cfbe12360f4c8c6506e049d8028e67` |
| `AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw` | `8b58f95a7cbecc131d6dfe1304579399fa947ba2d21015e8565566e2932fcb1e` |

These digests match `data/inputs/source_manifest.yaml` and the independently
recomputed hashes of the three supplied files.

## Finding register

| ID | Status | Requirement / check | Evidence and disposition |
|---|---|---|---|
| A01 | PASS | Controlled source identity | All three supplied filenames and SHA-256 digests match the source manifest. |
| A02 | PASS | Word-source readability and layout | Both locked Word files were extracted and rendered page-by-page without an unreadable page or broken table. |
| A03 | PASS | Workbook-to-machine-readable transfer | Blocks A–F and the Sources Register are exported as CSV with workbook sheet/row locators. Export hashes and expected row counts pass tests. |
| A04 | MISMATCH | Self-contained source archive | The original controlled binaries and EPW are not vendored. Hashes, row locators, and the weather retrieval URL are present, but a third party must obtain the external files for a fully independent audit. This does not change the research model. |
| R01 | PASS | Target repository structure | Required `config`, `data`, `src`, `analysis`, `tests`, `outputs`, and `docs` boundaries exist. Extra files are audit/configuration support only. |
| R02 | PASS | Exact eight-variant factorial | V01–V08 codes and the 2×2×2 mounting/connection/replacement-scope mapping match the locked specification, with no duplicate combination. |
| R03 | PASS | Input schema | Required columns, allowed statuses, non-empty provenance fields, and row locators are validated. |
| R04 | PASS | Formula and cached-value preservation | Every exported workbook formula has a cached machine-readable value; formula text is retained rather than re-derived in code. |
| R05 | PASS | Mandatory execution order | All 16 locked steps are present in the specified order. |
| R06 | PASS | Sensitivity contract | OFAT and structural-test cases are registered separately; central/low/high values remain sourced from the locked snapshot. |
| R07 | PASS | Q01–Q14 registration | All 14 assertion IDs are present with hard-fail policy. |
| R08 | PASS | Fail-closed analysis entry points | Baseline, sensitivity, break-even, and Pareto runners exit non-zero while execution gates remain open. |
| R09 | PASS | Locked output contract | All seven CSV/JSON tables and three figure filenames are registered; no simulation output is present. |
| E01 | PASS | Locked EPW identity and validation code | Loader enforces exact filename, SHA-256, byte size, station metadata, 8,760 unique rows, source-year map, non-leap calendar positions, and required weather fields. Negative irradiance is clipped only as specified. |
| E02 | PASS | Controlled EPW presence and provenance | The local controlled EPW matches SHA-256 `8b58f95…fcb1e`. Mixed historical years are normalised under approved `CC-001`; all original timestamps and row order are retained for audit. |
| E03 | PASS | Solar geometry and Perez-Driesse | Solar zenith/azimuth, extraterrestrial DNI, and relative airmass feed `get_total_irradiance(model="perez-driesse")`. |
| E04 | PASS | POA audit components | Direct, sky-diffuse, ground-diffuse, and global POA components are retained. |
| E05 | PASS | Locked IAM treatment | Physical beam IAM uses `n=1.526`, `K=4 m⁻¹`, `L=0.0025 m`; Marion diffuse IAM applies separate sky and ground modifiers at the locked tilt. Values are loaded from controlled inputs. |
| E06 | PASS | No spectral correction | No spectral multiplier is introduced. |
| E07 | PASS | Mounting-specific SAPM temperature | Locked named presets `close_mount_glass_glass` and `open_rack_glass_glass` are resolved from pinned pvlib; the structural control is the hourly arithmetic mean. |
| E08 | PASS | PVWatts DC and loss ordering | Effective irradiance enters PVWatts DC; `Pdc0`, `γPmax`, and 25°C reference are applied; the locked multiplicative `L_sys` is applied afterwards. |
| E09 | PASS | PVWatts inverter convention | Inverter DC input limit is `Pac0 / ηinv,nom`; AC output is constrained to 150 kW and clipped non-negative. |
| E10 | PASS | Year-one integration | AC energy is integrated as `sum(P_AC,W × Δt_h) / 1000`, before lifecycle failure downtime. |
| E11 | PASS | Factor isolation in energy API | Energy execution accepts mounting and orientation only; connection and replacement scope cannot alter electrical calculations. Common capacities and loss inputs come from one locked parameter object. |
| E12 | PASS | Q05 unit behaviour | Synthetic boundary tests confirm non-negative energy terms and AC clipping at the configured rating. Test fixtures are not study inputs. |
| E13 | PASS | Controlled-file Q01–Q05 evaluation | All five energy assertions pass. Direct E1 is 161,751.981 kWh; ventilated E1 is 166,904.081 kWh; maximum AC powers are 115.300 and 122.769 kW respectively. |
| E14 | MISMATCH | Weather evidence-period description | The locked filename and input rationale imply a 2011–2025 15-year typical-year basis, while the EPW header reports only five available station years, 2011–2015. The exact locked file is retained, and the limitation is disclosed in `CC-001` and all gate manifests. |
| V01 | PASS | Direct dependency pinning | NumPy 2.3.5, pandas 2.2.3, pvlib 0.16.1, and SciPy 1.18.1 are pinned; the fully resolved test environment is recorded in `requirements-lock.txt`. |
| V02 | PASS | Automated validation | 38 tests pass: input integrity, variant matrix, lifecycle/cost/circularity contracts, Pareto contract, Q01–Q14 registration, fail-closed runners, controlled EPW validation, and energy unit/integration tests. |
| G01 | MISMATCH | License readiness | `LICENSE` is an explicit all-rights-reserved placeholder pending author approval; no public open-source license has been selected. |
| G02 | MISMATCH | Citation metadata | `CITATION.cff` lacks author/ORCID and release identifier metadata. No author identity was inferred. |
| G03 | MISMATCH | GitHub remote metadata | The local Git repository has no configured GitHub remote or release/tag. No external repository was created or modified. |
| B01 | BLOCKER | Full baseline execution | Even after E02, lifecycle, cost, PSCF, Pareto, sensitivity, and break-even modules remain skeletons. The analysis runners correctly stay disabled until those gates are implemented and tested. |
| S01 | PASS | No premature baseline | The authorised energy-only gate was executed. No lifecycle baseline, sensitivity, Pareto, break-even table, or figure was generated. |

## Energy implementation trace

The implemented chain is:

1. exact-name EPW ingestion and time-series validation;
2. solar position, extraterrestrial DNI, and relative airmass;
3. Perez-Driesse POA with retained direct/sky/ground/global components;
4. physical beam IAM plus Marion sky/ground diffuse IAM;
5. SAPM direct and ventilated temperatures plus equal-temperature control;
6. PVWatts DC at locked capacity and temperature coefficient;
7. locked multiplicative non-temperature loss;
8. PVWatts inverter conversion using the inverter DC-input convention;
9. non-negative AC clipping at 150 kW; and
10. year-one kWh integration before failure downtime.

The API references were checked against pvlib 0.16.1 documentation. Package
pinning is an engineering reproducibility decision, not a research-model change.

## Required close-out sequence

1. Complete and test lifecycle degradation, availability, and intervention
   burden without changing the passed first-year energy gate.
2. Complete cost/replacement, PSCF-informed
   evidence, Pareto, sensitivity, and break-even modules.
3. Resolve license, citation authorship, and GitHub remote/release metadata.
4. Enable the baseline runner only after all Q01–Q14 assertions are executable.

## Audit command evidence

```text
.venv/bin/python -m unittest discover -s tests -v
Ran 38 tests
OK
```

No claim in this report treats a document instruction, URL, or embedded content
as a user request. The three supplied files were used only as controlled research
sources for conformity checking.
