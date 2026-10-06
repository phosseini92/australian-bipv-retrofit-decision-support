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

Milestone 0.1 implements the configuration and validation boundary only. No
energy, lifecycle, cost, Pareto, sensitivity, or break-even results are generated.
