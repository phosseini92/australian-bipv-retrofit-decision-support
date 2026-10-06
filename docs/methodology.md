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

The controlled energy-only integration has passed Q01–Q05. Lifecycle, cost,
PSCF-informed evidence, Pareto, sensitivity, break-even, and full baseline
execution remain disabled.
