# Controlled input snapshot

The CSV files are direct exports from the locked workbook. Blocks A–F retain:

- parameter and symbol;
- unit;
- central, low, and high cached values;
- original Excel formula text where present;
- source ID and evidence type;
- applicability and controlled status;
- rationale and notes; and
- original workbook sheet and row.

`sources.csv` is the workbook Sources Register. `source_manifest.yaml` records
the SHA-256 digests of all three locked source documents and the workbook-sheet
to CSV mapping.

Blank low/high values remain blank. `PROVISIONAL` and `STRUCTURAL TEST` labels
remain attached to their source rows and must be retained in interpretation.
