# Controlled input status

This repository does not add research assumptions. Every model input is copied
from the locked workbook and retains one of four source statuses:

- `LOCKED`: accepted controlled input or rule.
- `DERIVED`: workbook formula with its cached value and formula text retained.
- `PROVISIONAL`: transferred evidence or proxy that must remain qualified.
- `STRUCTURAL TEST`: diagnostic or threshold setting, not an asserted market or
  physical fact.

The CSV snapshot preserves blank low/high values rather than filling them. The
code must not substitute defaults for missing values or convert missing values to
zero. Any future change to a controlled value must occur in a versioned source
artifact before it is reflected in code.
