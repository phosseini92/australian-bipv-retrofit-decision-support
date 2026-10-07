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

`CC-001` is not an added research assumption. It is an approved engineering
normalisation that replaces only the mixed historical year labels in the TMYx
index. All 8,760 source rows, values, calendar positions, and original
timestamps are preserved and audited.

The central cost gate records access cost and end-of-life removal cost as zero
only because the locked specification excludes unsupported tariffs from the
central accounting and reserves them for break-even/stress analysis. These
bookkeeping zeros must not be described as evidence that access or removal is
costless. Likewise, the reported transport component is contained within the
all-in recycling fee and is never added to it.

Approved `CC-002` resolves the three Break-even contract questions without
changing central inputs. Full discounted WLC equality is primary for
`BE_access`; the initial-premium equation remains diagnostic. All four matched
reversible/low pairs are evaluated symmetrically for `BE_r`. Intervention
frequency remains a numerical OFAT input and is not promoted to an unsupported
independent threshold. These are explicit change-control decisions, not silent
modelling defaults.
