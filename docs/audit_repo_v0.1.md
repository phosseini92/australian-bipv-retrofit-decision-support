# Formal Audit — Repo v0.1 through Pareto Structural Robustness Gate

Audit date: 2026-10-07
Audit scope: repository structure, controlled inputs, locked variant/design
contract, QA registration, energy, lifecycle-energy, cost, and PSCF-informed
evidence implementation, and readiness to run.
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
- Lifecycle-energy gate: **PASS** — locked degradation, availability,
  intervention-burden, and scheduled-year equations pass their scoped QA.
- Lifecycle-cost gate: **PASS** — locked initial, recurring, corrective,
  inverter, EoL, discounting, WLC, and cost-intensity equations pass.
- PSCF-informed Evidence Gate: **PASS** — item-level evidence coding, central
  dimensions, GAP-excluded robustness, and Q11/Q14 pass.
- Central primary Pareto Gate: **PASS** — raw seven-criterion dominance,
  pairwise QA, and Q12/Q14 pass without weights or normalization.
- Pareto structural robustness gate: **PASS** — primary/combined-CIRC ×
  GAP-zero/excluded set comparison and robustness QA pass.
- Baseline-execution gate: **BLOCKED** — no baseline was run.
- Public GitHub-release gate: **HOLD** — license, citation authorship, and remote
  repository metadata remain unresolved.

Summary: **61 PASS / 5 MISMATCH / 1 BLOCKER** across 67 checks.

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
| R08 | PASS | Fail-closed final analysis entry points | Baseline, sensitivity, break-even, and final Pareto runners exit non-zero while downstream gates remain open. Separate controlled gate runners do not emit the locked final baseline outputs. |
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
| L01 | PASS | Locked lifecycle input binding | `T`, `d`, `N_mod,eq`, `λ_mod`, `DT_event`, handled/replaced scopes, disturbed areas, `k_rev,time`, and inverter service life are read from the controlled snapshot without defaults. |
| L02 | PASS | Derived failure consistency | The implementation recomputes `f_fail = N_mod,eq × λ_mod` and `N_fail(T) = f_fail × T`, hard-failing if they differ from the locked cached workbook values. |
| L03 | PASS | Linear degradation | Every annual factor uses `max(0, 1 - d×(y-1))`; year 1 is unchanged and no compound recursion or second LID deduction is present. |
| L04 | PASS | Expected availability | Availability uses the locked failure rate, downtime, disturbed-area fraction, 8,760-hour denominator, clipping, and energy-weighted lifetime ratio. It remains separate from `L_sys`. |
| L05 | PASS | Intervention and material burden | Cumulative disturbed area and handled scope follow the locked equations. Exactly one failed product is replaced per event; adjacent assembly products do not inflate replacement mass. The 25.5-kg unit mass is recovered exactly from locked `M_EOL × 1000 / N_mod,eq`. |
| L06 | PASS | Scheduled inverter years | Service-life multiples strictly within the horizon reproduce the locked cases: year 15 for T=25/30 and years 15 and 30 for T=35. The common monetary allowance is verified in K05. |
| L07 | PASS | Controlled lifecycle-energy integration | All eight variants produce finite, non-negative 30-year metrics. Scoped Q04, Q06–Q09, and Q14 checks pass; connection has no assumed time benefit, and replacement scope affects net energy only through disturbed-area availability. |
| K01 | PASS | Locked cost input binding | Currency basis, horizon, discount rate, mounting and reversibility costs, O&M, corrective material, inverter, recycling, recovery, and EoL rules are loaded from the controlled snapshot without numeric defaults. |
| K02 | PASS | Cached cost derivations | `C_direct`, `C_vent`, `ΔC_rev`, cached O&M values, failed-product material cost, recycling decomposition, and owner recovery are independently recomputed and hard-fail on mismatch. |
| K03 | PASS | Initial and O&M cost | Each variant follows `C0 = A_BIPV × C_mount + C_rev`; annual O&M is `m_OM × C0`. The 5% reversibility premium remains visibly tagged as a structural-test point. |
| K04 | PASS | Corrective replacement bookkeeping | Expected annual material cost is `f_fail × C_rep,mat`. Exactly one failed product is costed per event, adjacent assembly products add zero material cost, and unsupported access tariffs remain excluded from central WLC. |
| K05 | PASS | Common inverter allowance | `C_inv,ref = p_invrep × (A_BIPV × C_BIPV)` is independent of mounting and reversibility premiums. Its nominal amount, year-15 schedule, and discounted PV are identical across V01–V08, closing Q08 for the cost gate. |
| K06 | PASS | End-of-life accounting | Central owner recovery is zero. EoL removal remains a break-even/stress variable. The transport component plus processing component reconciles to the all-in recycling fee and is not added a second time. |
| K07 | PASS | Discounted WLC and cost intensity | End-of-year recurring costs, scheduled inverter replacement, and terminal EoL cost reconcile to component present values and WLC. `CostIntensity = WLC/E_life`; electricity revenue is not inserted into WLC. |
| K08 | PASS | Controlled cost integration | All eight variants produce finite, non-negative cost outputs. Internal C01–C04 and formal Q08–Q10/Q14 checks pass. Replacement scope creates no unsupported central WLC difference. |
| P01 | PASS | PSCF method boundary | The published PSCF remains qualitative. Repository outputs use the locked label “PSCF-informed evidence-readiness” and do not present the study-specific code as a native PSCF score. |
| P02 | PASS | Item-level evidence registry | All 13 mechanistic, institutional, and contextual items retain value, evidence state, input status, source ID, sheet, and row provenance. Variant factors affect only `M_REV` and `M_REP`. |
| P03 | PASS | Central dimension reconciliation | Item arithmetic reproduces locked M profiles 0.25/0.50/0.50/0.75, common I=0.70, common C=0.50, and combined values 0.4833/0.5667/0.5667/0.65. |
| P04 | PASS | GAP structural treatment | `M_DFD_DOC` and `I_TAKE` are the only excluded GAP items. Dimensions are recomputed from item labels; `C_LOG` remains an explicit zero constraint in the contextual denominator. |
| P05 | PASS | Factor isolation | Institutional and contextual dimensions are identical across V01–V08; direct versus ventilated mounting produces no evidence-readiness difference. Q11 passes. |
| P06 | PASS | Evidence numerical integrity | Central and GAP-excluded M/I/C/combined values are finite and bounded in [0,1]. The combined structural criterion is an unweighted arithmetic mean. Q14 passes. |
| PA01 | PASS | Locked primary vector | `E_life`, `A_life`, `WLC`, `B_dist`, `M`, `I`, and `C` are evaluated in their locked directions. Institutional and contextual values remain constant and are not fabricated. |
| PA02 | PASS | Dominance rule | A variant must be no worse on every raw criterion and strictly better on at least one. The only tolerance is eight machine ULPs for floating-point noise. |
| PA03 | PASS | No preference transformation | No weighting, normalization, composite score, or practical-equivalence band is used. Q12 passes. |
| PA04 | PASS | Dominance graph | Six directed dominance edges are reproduced: V02→V01/V03, V04→V03, V06→V05/V07, and V08→V07. The graph is irreflexive and asymmetric. |
| PA05 | PASS | Central non-dominated set | The primary central set is V02, V04, V06, and V08. Each remaining assembly-level variant has at least one valid incoming dominance edge. |
| PA06 | PASS | Central-gate scope isolation | The central-primary runner itself emits no structural, OFAT, break-even, final CSV, or figure output. Structural robustness is executed only by the separate controlled gate below. All central raw metrics are finite; Q14 passes. |
| PR01 | PASS | Structural-run contract | The full primary/combined-CIRC × GAP-zero/excluded matrix is executed from the two locked named structural runs, including their joint condition. |
| PR02 | PASS | Criterion replacement | Combined runs replace exactly M/I/C with CIRC; E_life, A_life, WLC, and B_dist remain unchanged and raw. |
| PR03 | PASS | GAP isolation | GAP exclusion changes only item-derived evidence dimensions. Non-evidence metrics remain bit-identical, and CIRC is recomputed as the unweighted M/I/C mean. |
| PR04 | PASS | Set stability | All four scenarios retain V02/V04/V06/V08. Every Jaccard similarity to central-primary is 1.0. |
| PR05 | PASS | Graph stability | All scenarios retain the same six dominance edges; no edge is created or removed by criterion representation or GAP treatment. |
| PR06 | PASS | Robustness scope | Q12 and Q14 pass. No numerical OFAT sensitivity, inclusion frequency, break-even, final baseline output, or figure is produced. |
| V01 | PASS | Direct dependency pinning | NumPy 2.3.5, pandas 2.2.3, pvlib 0.16.1, and SciPy 1.18.1 are pinned; the fully resolved test environment is recorded in `requirements-lock.txt`. |
| V02 | PASS | Automated validation | 91 tests pass: input integrity, variant matrix, energy/lifecycle/cost/evidence/Pareto contracts, item-level GAP handling, raw and structural dominance behaviour, Q01–Q14 registration, fail-closed final runners, controlled EPW validation, and all implemented gate equations. |
| G01 | MISMATCH | License readiness | `LICENSE` is an explicit all-rights-reserved placeholder pending author approval; no public open-source license has been selected. |
| G02 | MISMATCH | Citation metadata | `CITATION.cff` lacks author/ORCID and release identifier metadata. No author identity was inferred. |
| G03 | MISMATCH | GitHub remote metadata | The local Git repository has no configured GitHub remote or release/tag. No external repository was created or modified. |
| B01 | BLOCKER | Full baseline execution | Numerical OFAT sensitivity and break-even remain incomplete. The baseline runner correctly stays disabled until those gates are implemented and tested. |
| S01 | PASS | No premature baseline | The authorised energy, lifecycle-energy, cost, Evidence, central primary Pareto, and Pareto robustness Gates were executed. No formal baseline, numerical sensitivity table, break-even table, locked final Pareto CSV, or figure was generated. |

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

1. Complete numerical OFAT sensitivity and break-even modules.
2. Resolve license, citation authorship, and GitHub remote/release metadata.
3. Enable the baseline runner only after all Q01–Q14 assertions are executable.

## Audit command evidence

```text
.venv/bin/python -m unittest discover -s tests -v
Ran 91 tests
OK
```

No claim in this report treats a document instruction, URL, or embedded content
as a user request. The three supplied files were used only as controlled research
sources for conformity checking.
