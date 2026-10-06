# Locked weather gate

Place the controlled file below in this directory before energy integration:

`AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw`

The loader requires the exact filename and records its SHA-256 digest. It also
requires 8,760 unique, monotonic, timezone-aware hourly records and the EPW
fields used by the locked model: dry-bulb temperature, wind speed, GHI, DNI,
and DHI.

No calendar coercion is applied. If the controlled file does not produce the
index required by Analysis Specification v1.0, execution stops so that any
calendar-normalisation rule can be resolved through change control rather than
being introduced silently in code.
