# CC-001 — TMYx mixed-year index and evidence-period disclosure

Status: **APPROVED FOR IMPLEMENTATION**  
Approval date: 2026-10-06  
Classification: engineering normalisation plus evidence disclosure  
Scientific model change: **none**

## Trigger

The exact locked file
`AUS_VIC_Melbourne.RO.948680_TMYx.2011-2025.epw` was supplied and verified at
SHA-256
`8b58f95a7cbecc131d6dfe1304579399fa947ba2d21015e8565566e2932fcb1e`.
It contains 8,760 data records and identifies Melbourne Regional Office, WMO
948680, at UTC+10.

Two source characteristics required explicit treatment before execution:

1. TMYx months retain their selected historical years, so the raw timestamp
   sequence moves backwards at several month boundaries and is not monotonic.
2. Although the package filename is labelled 2011–2025, `COMMENTS 1` reports
   five available station years with period of record 2011–2015. The monthly
   selections are January 2014, February 2012, March 2014, April 2013, May 2015,
   June 2012, July 2014, August 2012, September 2014, October 2011, November
   2012, and December 2011.

## Approved index rule

- Preserve all 8,760 rows in source-file order.
- Require the source month/day/hour sequence to match a complete non-leap year.
- Use the EPW fixed standard-time offset, UTC+10; do not introduce daylight
  saving time.
- Replace only the mixed source-year index with the non-leap reference calendar
  2001-01-01 00:00 through 2001-12-31 23:00.
- Retain every original source timestamp and year in the hourly audit frame.
- Hard-fail on a leap day, missing/duplicate record, unexpected calendar
  position, hash mismatch, or changed metadata.

The reference year is an indexing device only. No weather value is interpolated,
deleted, duplicated, reordered, or rescaled.

## Evidence treatment

The locked input row and filename are not silently rewritten. Outputs and
manifests must distinguish:

- nominal TMYx package label: `2011-2025`; and
- EPW-reported available station record: `2011-2015`.

Accordingly, claims must not describe this file as containing fifteen complete
years of measured station meteorology. This is an evidence-description mismatch,
not a change to the selected weather file.

## Impact assessment

- Variant definitions: no impact.
- Weather values and row order: no impact.
- Solar-model settings: no impact.
- Lifecycle/cost/PSCF/Pareto rules: no impact.
- Reproducibility: improved through explicit hash, calendar checks, retained
  source timestamps, and manifest disclosure.
