# Data-source provenance

`data/inputs/sources.csv` reproduces the complete locked Sources Register. Each
input row references one or more source IDs and retains its original workbook
sheet and row.

The three controlled artifacts and their SHA-256 digests are recorded in
`data/inputs/source_manifest.yaml`. The machine-readable export was generated
from the workbook's stored formulas and cached values. The source workbook was
not modified.

The controlled weather identity and retrieval URL are stored in
`data/weather/weather_manifest.json`. The verified local EPW has SHA-256
`8b58f95a7cbecc131d6dfe1304579399fa947ba2d21015e8565566e2932fcb1e`;
the data file is Git-ignored, while the manifest and validation rule are tracked.

The nominal package label is 2011–2025, but the EPW header reports five
available station years (2011–2015). `CC-001` preserves this distinction and
defines the audit-safe mixed-year index normalisation used for energy modelling.
