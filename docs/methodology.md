# Locked methodology contract

The study is a deterministic, reproducible lifecycle decision analysis of eight
BIPV façade retrofit configurations for a common Melbourne Class 5 commercial
office reference archetype.

The variants form a complete 2×2×2 design across mounting, connection
reversibility, and replacement scope. These factors vary independently. The
configuration does not define a progressively better A–B–C hierarchy and does
not pre-label a variant as circular.

The mandatory execution order is stored in `config/model.yaml`. It begins with
input and manifest validation, proceeds through hourly energy, lifecycle,
whole-life cost, PSCF-informed evidence, Pareto, sensitivity, and break-even
analysis, and exports only after Q01–Q14 pass.

The post-audit energy gate implements weather validation, solar geometry,
Perez-Driesse POA irradiance, physical direct and Marion diffuse IAM,
mounting-specific SAPM temperature, the equal-temperature structural control,
PVWatts DC, multiplicative non-temperature losses, PVWatts inverter conversion,
AC clipping, and year-one energy integration. All numerical study inputs are
read from the controlled snapshot; the named SAPM presets are resolved from the
pinned pvlib version.

The exact locked EPW has passed hash, size, station-metadata, record-count,
calendar, and source-year-map validation. Its mixed historical years are
normalised under `CC-001` without changing row order or weather values, and the
original timestamps remain in the hourly audit frame.

The controlled energy-only integration has passed Q01–Q05. The next controlled
gate propagates those first-year results through the locked linear degradation
factor `max(0, 1 - d*(y-1))`, the expected-event availability approximation,
and the locked intervention-burden equations. Availability remains separate
from the year-one loss stack. Assembly-level adjacent products are temporary
handling scope only: exactly one failed product is permanently replaced per
event, so replacement material mass is common across variants.

The degradation → availability → lifecycle-energy integration gate has passed
Q04, Q06, Q07, Q09, Q14, and the scheduled-year prerequisite for Q08. The
cost gate then applies the locked initial-cost, O&M, corrective material,
inverter, EoL, discounting, WLC, and cost-intensity equations. Q08 is closed for
the central cost implementation because both the nominal and discounted
inverter allowance are common across variants.

The central accounting assigns no unsupported access or EoL-removal tariff.
The corresponding zero values mean exclusion from the central WLC, not that
those services are costless; they remain explicit break-even/stress variables.
The all-in recycling fee already contains transport, so its transport component
is reported as a decomposition and is not added again. Electricity is not
monetised inside WLC because lifetime electricity remains a separate decision
criterion.

The Evidence Gate operationalises the locked, study-specific 0/0.5/1
evidence-readiness code at item level. It does not treat that code as a native
PSCF score. The central run retains documented evidence gaps as zero and flags
them; the structural robustness run recomputes each affected dimension after
excluding only GAP-labelled items. Explicit documented constraints remain zero
and stay in their denominators. The combined structural criterion is the
unweighted arithmetic mean of M, I, and C, exactly as locked.

The central primary Pareto Gate uses raw `E_life`, `A_life`, `WLC`, `B_dist`,
`M`, `I`, and `C` values with their locked maximise/minimise directions. A
variant dominates another only when it is no worse on every criterion and
strictly better on at least one. No weights or normalization are applied. The
implementation tolerance is limited to eight machine ULPs, solely to suppress
floating-point noise. Institutional and contextual criteria remain in the
vector and are reported as constant; no artificial differences are introduced.

Criterion-structure/GAP robustness is evaluated as a complete 2×2 matrix:
three separate M/I/C dimensions versus the combined CIRC criterion, each under
central GAP-as-zero and GAP-excluded dimension arithmetic. CIRC is recomputed
from item-derived M/I/C values and introduces no weights. Scenario sets are
compared to central-primary with Jaccard similarity, treated as a robustness
summary rather than a probability.

Numerical sensitivity follows the registered one-factor-at-a-time contract:
each valid run substitutes exactly one locked low or high endpoint and
recomputes every dependent lifecycle and cost quantity before repeating the raw
primary Pareto analysis. Module-service-life endpoints change the evaluation
horizon to 25 or 35 years without creating an artificial module replacement;
the corresponding inverter schedule remains year 15 for T=25 and years 15 and
30 for T=35. The 24 registered endpoint evaluations contain 23 valid
changed-input runs because locked `V_rec` low equals its central value of zero.
That duplicate endpoint is retained in the audit trail but excluded from the
Pareto-inclusion denominator. Inclusion frequency and Jaccard similarity are
reported only as deterministic robustness summaries, never probabilities.

The two energy structural runs repeat the complete downstream lifecycle, cost,
evidence, and primary Pareto chain. West orientation substitutes only the
locked west azimuth. The equal-temperature control uses the hourly arithmetic
mean temperature result for both mounting categories and otherwise leaves the
central chain unchanged.

Break-even calculations implement the five named output families without
inventing unsupported tariffs. Under approved `CC-002 D1-B`, full discounted
WLC equality is the primary access/intervention-saving threshold; the literal
initial-premium-only Section 11.2 value remains a labelled diagnostic. D2-A
makes all four matched reversible/low comparisons the symmetric primary
`BE_r` set over 0–15% real. D3-A keeps intervention frequency as the registered
`λ_mod`/`f_fail` OFAT input and does not create an unsupported independent
threshold. Missing and non-unique roots always use explicit status strings and
null values rather than NaN/Inf.

The formal baseline runs only after all parent Gate assertions pass. Its six
CSV tables, manifest, and three figures are first written to a staging
directory, hashed, and then moved into the locked output locations. This export
workflow is an engineering reproducibility control and does not alter a model
input, equation, criterion, or decision rule.
