# Data-source provenance

`data/inputs/sources.csv` reproduces the complete locked Sources Register. Each
input row references one or more source IDs and retains its original workbook
sheet and row.

The three controlled artifacts and their SHA-256 digests are recorded in
`data/inputs/source_manifest.yaml`. The machine-readable export was generated
from the workbook's stored formulas and cached values. The source workbook was
not modified.

The weather filename is locked in Block B. The EPW file is not bundled in
milestone 0.1, and no weather download or simulation occurs at this gate.
