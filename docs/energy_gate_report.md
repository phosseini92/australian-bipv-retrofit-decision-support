# Controlled Energy Integration Gate — Q01–Q05

Run date: 2026-10-06  
Status: **PASS**  
Baseline executed: **No**

## Controlled weather

- File: `AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw`
- SHA-256: `8b58f95a7cbecc131d6dfe1304579399fa947ba2d21015e8565566e2932fcb1e`
- Station: Melbourne Regional Office, WMO 948680
- Records: 8,760 hourly rows
- Time basis: fixed UTC+10, no daylight-saving transformation
- Normalised audit index: 2001-01-01 00:00 through 2001-12-31 23:00
- Source timestamps: retained in the hourly audit frame
- Nominal package label: 2011–2025
- EPW-reported available record: 2011–2015

Required-field range checks also pass: dry-bulb temperature 2.8–43.2 °C, wind
speed 0.0–12.1 m/s, GHI 0–1,072 W/m², DNI 0–1,013 W/m², and DHI 0–447 W/m²,
with no missing value in any required series.

The calendar rule and evidence-period disclosure are controlled by `CC-001`.
No weather value was removed, interpolated, duplicated, reordered, or rescaled.

## Runtime

| Package | Version |
|---|---:|
| NumPy | 2.3.5 |
| pandas | 2.2.3 |
| pvlib | 0.16.1 |
| SciPy | 1.18.1 |

## Central north-orientation energy results

| Metric | Direct mount | Ventilated mount |
|---|---:|---:|
| Year-one AC energy before failure downtime | 161,751.981 kWh | 166,904.081 kWh |
| Maximum AC power | 115.300 kW | 122.769 kW |
| AC clipping hours at 150 kW | 0 | 0 |
| Effective irradiance | 1,115.291 kWh/m² | 1,115.291 kWh/m² |
| Mean cell temperature | 22.052 °C | 19.845 °C |
| Maximum cell temperature | 67.140 °C | 56.433 °C |

Ventilated-mount energy is 5,152.101 kWh (3.185%) higher than direct-mount
energy in this controlled year-one calculation. This difference is a computed
output of the locked mounting-temperature proxies, not an added assumption.

## Locked assertions

| Assertion | Status | Evidence |
|---|---|---|
| Q01 | PASS | Area, PV technology, nominal DC capacity, inverter family, and AC rating are identical across V01–V08. |
| Q02 | PASS | V01–V04 share the direct result; V05–V08 share the ventilated result. |
| Q03 | PASS | Reversibility changes no electrical result. |
| Q04 | PASS | Replacement scope changes no first-year energy result. |
| Q05 | PASS | All audited energy arrays are finite and non-negative; maximum AC power remains below 150 kW. |

## Gate boundary

This report validates only weather ingestion and the first-year energy chain.
It is not `variant_central.csv`, does not include failure downtime or degradation,
and must not be cited as the completed lifecycle baseline. The next authorised
implementation gate is degradation, availability, and lifecycle energy.
